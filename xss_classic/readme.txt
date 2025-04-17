sort -u validated_urls.txt -o validated_urls.txt
python3 new_constructed_tool.py 
sort constructed_urls.txt > sorted_urls.txt
