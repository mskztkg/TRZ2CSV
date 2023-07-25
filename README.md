
Description:  
  trz2csv is coverter from TRZ format to CSV.
  TRZ is one of xml formats used in the record for 
  the RTR series by T&D.
  
Usage:  
  `python trz2csv.py -f single_file.trz`
    -> output is converted csv file named `single_file.csv`
    
  `python trz2csv.py -l multiple_file_list.txt`
    -> output is marged single csv file named `multiple_file_list.csv`
    
  input `multiple_file_list.txt` looks like:  
    ```
    single_file01.trz
    single_file02.trz
    single_file03.trz
    single_file04.trz
    ......
    ```   
  You can change output file name by `-o` option:  
    `python trz2csv.py -f single_file.trz -o output.csv`  
    `python trz2csv.py -l multiple_file_list.txt -o marged_output.csv`  
    
