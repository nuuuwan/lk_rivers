import json
import os


def main():
    DIR_RIVERS = os.path.join("data", "rivers")
    main_riv_id_to_file_size = {}
    for file_name in os.listdir(DIR_RIVERS):
        if not file_name.endswith(".geojson"):
            continue
        riv_id = file_name.replace(".geojson", "")
        file_path = os.path.join(DIR_RIVERS, file_name)
        file_size = os.path.getsize(file_path)
        main_riv_id_to_file_size[riv_id] = file_size

    idx = {}
    for riv_id, file_size in list(
        sorted(
            main_riv_id_to_file_size.items(),
            key=lambda item: item[1],
            reverse=True,
        )
    )[10:20]:
        print(riv_id, file_size)
        url = f"https://github.com/nuuuwan/lk_rivers/blob/main/data/rivers/{riv_id}.geojson"
        os.system(f'open "{url}"')
        idx[riv_id] = "XXXXX"

    print(json.dumps(idx, indent=2))


if __name__ == "__main__":
    main()
