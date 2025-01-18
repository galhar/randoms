directory=$1
ssh newton "find $directory -type f -path '*/*30000/point_cloud.ply'" | while read -r file; do
	object_name=$(echo "$file" | awk -F'/' '{print $(NF-4)}')
	scp newton:"$file" $object_name.ply
done
