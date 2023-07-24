import sys
import os
import xml.etree.ElementTree as ET
import base64
import pandas as pd
import math
import numpy as np
# import matplotlib.pyplot as plt
from datetime import datetime, timezone, timedelta


class channel_data:
    def __init__(self, channel):
        # 変換式のカテゴリ、別紙[記録データ変換仕様]参照
        data_format_spec = { # 'type':['channel_index', 'unit', 'convert_format', 'with_time']
                            '13':['temperature',r'[°C]','3.1.1', False],
                            '208':['humidity',r'[%]','3.1.2', False],
                            '209':['humidity',r'[%]','3.1.3', False],
                            '269':['temperature',r'[°C]','3.8.1', True],
                            '464':['humidity',r'[%]','3.8.2', True],
                            '465':['humidity',r'[%]','3.8.3', True],
                            '73':['illuminance',r'[lx]','3.2.1', False], 
                            '329':['accum_illuminance',r'[lxh]', '3.3.1', True],
                            '85':['UV_intensity',r'[mW/cm2]','3.2.2', False],
                            '341':['accum_UV',r'[mW/cm2h]', '3.3.2', True],
                            '129':['Current',r'[mA]', '3.4.1', False],
                            '146':['Voltage',r'[mV]', '3.4.2', False]
        }
        self.ch= channel
        self.ch_type = self.ch.findtext('type')
        if self.ch_type in data_format_spec.keys():
            # タイムゾーン （秒）夏時間設定('dst_bias')無し
            self.timezone_offset  = timezone(timedelta(minutes=(int(self.ch.findtext('time_diff')) + int(self.ch.findtext('std_bias'))))) 
            self.set_ch_spec(
                data_format_spec[self.ch_type][0],
                data_format_spec[self.ch_type][1],
                data_format_spec[self.ch_type][2],
                data_format_spec[self.ch_type][3]
            )
        else:
            if self.ch_type == '':
                print('Channel type is not defined.')
            else:
                print('Channel type is unknown. Channel type: %s' % self.ch_type)
            return None
        # return self


    def set_ch_spec(self, ch_name, unit, conv_format, with_time):
        self.ch_name = '{0} ch.{1} {2}{3}'.format(self.ch.findtext('name'),self.ch.findtext('num'), ch_name, unit)
        # Ondotori, RTR series XML convert specificaton
        self.conv_format = conv_format
        # data with time: True, data without time (start time / interval / count):False
        self.time_inc = with_time

    
    def format_time(self, u_time):
        dt = datetime.fromtimestamp(u_time, self.timezone_offset)
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    
    def get_time_list(self):
        # UNIXタイム(秒)
        unix_time = int(self.ch.findtext('unix_time'))
        # 測定の間隔を秒単位で取得
        interval = int(self.ch.findtext('interval'))
        # 測定のカウント数を取得
        count = int(self.ch.findtext('count'))
        time_list=[]
        for i in range(count):
            time_list.append(self.format_time(unix_time + i*interval))
        return  time_list

    def data2reading(self, set_data):
        if set_data == 0xEEEE:
            return ''
        elif self.conv_format[0:3] == '3.1' or self.conv_format == '3.8': # 温度、 湿度
            reading = float((set_data - 1000) / 10)
            dp = 0 if self.conv_format == '3.1.2' else 1
            return self.round_float(reading, digits=4, decimal_places=dp) 
        elif self.conv_format[0:3] == '3.2' or self.conv_format[0:3] == '3.3': # 照度、紫外線強度
            exp = (set_data & 0xF000) >> 12 # 2の指数部を取得
            frac = set_data & 0x0FFF # 仮数部を取得
            denomin = 100 if self.conv_format == '3.2.1' else 1000
            denomin = 1 if self.conv_format == '3.3.1' else denomin
            reading = float((frac * 2**exp) / denomin) # 照度/紫外線強度に変換
            dp = 2 if self.conv_format == '3.2.1' else 3
            dp = 0 if self.conv_format == '3.3.1' else dp
            return self.round_float(reading, digits=4, decimal_places=dp) 
        elif self.conv_format[0:3] == '3.4': # 電流、電圧、CO2、騒音
            sign_bit = (set_data & 0b1000000000000000) >> 15 # 符号部を取得
            sign = 1 if sign_bit == 0 else -1
            exp = (set_data & 0b0111000000000000) >> 12 # 2の指数部を取得
            frac = set_data & 0b0000111111111111 # 仮数部を取得
            denomin = 100 if self.conv_format == '3.4.1' else 10
            denomin = 1 if self.conv_format == '3.4.3' else denomin
            reading = float(sign * (frac * 2**exp) / denomin) 
            dp = 2 if self.conv_format == '3.4.1' else 1
            dp = 0 if self.conv_format == '3.4.3' else dp
            return self.round_float(reading, digits=4, decimal_places=dp) 
        else:
            return None

    def decode_data(self):
        bytes_data = base64.b64decode(self.ch.findtext('data')) # Base64をバイナリデータに変換
        data_list = []
        if self.time_inc:
            byte_count = 10
            time_list = []
        else:
            byte_count = 2
            time_list = self.get_time_list()
        for i in range(0, len(bytes_data), byte_count):
            if self.time_inc:
                time = self.format_time(int.from_bytes(bytes_data[i:i+8], byteorder='little'))
                time_list.append(time)
                set_data = int.from_bytes(bytes_data[i+8:i+10], byteorder='little')
            else:
                set_data = int.from_bytes(bytes_data[i:i+2], byteorder='little')
            reading = self.data2reading(set_data)
            data_list.append(str(reading))

        return time_list, data_list

    def round_float(self, num, digits=4, decimal_places=2):
        if num == 0:
            return 0.0
        num_digits = int(math.log10(abs(num))) + 1 # numの絶対値の桁数を取得
        if num_digits >= digits: #実数が有効桁数以上の場合
            return float(int(num / 10**(num_digits - digits))) * 10**(num_digits - digits)
        else: # 小数点以下を桁上げして割戻し、有効少数点桁数で丸める
            return round(float(int(num * 10**(digits - num_digits)))/10**(digits - num_digits), decimal_places)


class TRZ2DF_coverter:
    def __init__(self, xml=None):
        self.reading_df = pd.DataFrame()
        if xml is not None:
            try:
                tree = ET.fromstring(xml)
            except ET.ParseError as e:
                print("XMLのフォーマットが正しくありません:", e)
            except Exception as e:
                print("エラー:", e)
            self.convert(tree)
            self.reading_df.sort_index(ascending=True, inplace=True)

    def append(self, other_convert):
        raw_list=list(self.reading_df.columns)
        raw_list_other=list(other_convert.reading_df.columns)
        if len(raw_list) == 0:
            self.reading_df = other_convert.reading_df
        else:
            if set(raw_list_other) <= set(raw_list):
                self.reading_df = pd.concat([self.reading_df, other_convert.reading_df], axis=0)
                self.reading_df.reset_index(inplace=True)
                self.reading_df.drop_duplicates(subset='Datetime', inplace=True, keep='first')
                self.reading_df.set_index('Datetime', inplace=True)
            elif set(raw_list_other).isdisjoint(set(raw_list)):# この辺のコード未検証
                self.reading_df = pd.concat([self.reading_df, other_convert.reading_df], axis=1)
                self.reading_df.sort_index(ascending=True, inplace=True)
            else:
                self.reading_df = pd.merge(self.reading_df, other_convert.reading_df, left_index=True, how='outer')
                self.reading_df.sort_index(ascending=True, inplace=True)

    def convert(self, doc_tree):
        for child_el in doc_tree:
            readings = []
            time_index = []
            if child_el.tag == 'ch':
                Ch_data = channel_data(child_el)
                if not Ch_data.ch_type:
                    continue
                else:
                    time_index, readings = Ch_data.decode_data()
                    item_df = pd.DataFrame([time_index, readings]).T
                    item_df.columns = ['Datetime', Ch_data.ch_name]
                    item_df.set_index('Datetime', inplace=True)
                    #print(item_df)
                self.reading_df = pd.merge(self.reading_df, item_df, how='outer', left_index=True, right_index=True)
        return None
    
    def print(self):
        print(self.reading_df)

    def write_CSV(self,filename):
        self.reading_df.to_csv(filename, index = True)
        
    def plot(self,filename):
        return None

# コマンドラインからの入力を処理
options = {'-f': True, '-l': True, '-o': True, '-h': False, '-p': True }
args = {'f': '', 'l': '', 'o': '', 'h': False , 'p': ''}
for key in options.keys():
    if key in sys.argv:
        idx = sys.argv.index(key)
        if options[key]:
            value = sys.argv[idx+1]
            if value.startswith('-'):
                raise ValueError(f'option {key} must have a value.')
            args[key[1:]] = value
            del sys.argv[idx:idx+2]
        else:
            args[key[1:]] = True
            del sys.argv[idx]

if args['f']:
    data_file = args['f']
    with open(data_file, mode='r', encoding = 'utf-8') as f:
        xml_doc = f.read()
    TRZ_data = TRZ2DF_coverter(xml_doc)
    TRZ_data.print()
    dir_name, file_name = os.path.split(data_file)
    basename, ext = os.path.splitext(file_name)
    out_file = args['o'] if args['o'] else dir_name + '/' + basename + '.csv'
    TRZ_data.write_CSV(out_file)
    if args['p']:
        plot_file = args['p'] if args['p'] else dir_name + '/' + basename + '.png'
        TRZ_data.plot(plot_file)

elif args['l']:
    list_file = args['l']
    TRZ_data = TRZ2DF_coverter()
    with open(list_file, mode='r', encoding = 'utf-8') as fl:
        for trz_filename in fl:
            trz_filename = trz_filename.strip()
            with open(trz_filename, mode='r', encoding = 'utf-8') as f:
                xml_doc = f.read()
            TRZ_single = TRZ2DF_coverter(xml_doc)
            TRZ_data.append(TRZ_single)
    TRZ_data.print()
    dir_name, file_name = os.path.split(list_file)
    basename, ext = os.path.splitext(file_name)
    out_file = args['o'] if args['o'] else dir_name + '/' + basename + '.csv'
    TRZ_data.write_CSV(out_file)
    if args['p']:
        plot_file = args['p'] if args['p'] else dir_name + '/' + basename + '.png'
        TRZ_data.plot(plot_file)
            
elif args['h']:
    help_txt = '''
Description:
  trz2csv is coverter from TRZ format to CSV.
  TRZ is one of xml formats used in the record for 
  the RTR series by T&D.
  
Usage:
  python trz2csv.py -f single_file.trz
    -> output is converted csv file named single_file.csv
    
  python trz2csv.py -l multiple_file_list.txt
    -> output is marged single csv file named multiple_file_list.csv
    
    input multiple_list.txt looks like:

      single_file01.trz
      single_file02.trz
      single_file03.trz
      single_file04.trz
      ......
  
  You can change output file name by -o option:
  python trz2csv.py -f single_file.trz -o output.csv
  python trz2csv.py -l multiple_file_list.txt -o marged_output.csv
    '''
    print(help_txt)
    sys.exit()
else:
    print('trz2csv is coverter from TRZ format to CSV.')
    sys.exit()

