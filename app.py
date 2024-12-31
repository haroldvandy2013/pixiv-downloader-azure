from datetime import datetime, timedelta
from typing import Literal
from flask import Flask, request, jsonify, render_template, send_file
from apscheduler.schedulers.background import BackgroundScheduler
from pixivpy3 import *
import os
import zipfile
import shutil

from pixiv_auth import refresh_and_get_token

app = Flask(__name__)

api = AppPixivAPI()
# pls add your own token here
token = ""
last_refresh_token_time = None

DOWNLOAD_FOLDER = "./downloads"

def fetch_image_urls(illust_id, size: Literal["large", "original"] = "large"):
    json_result = api.illust_detail(illust_id)
    illust = json_result.illust

    allPages = illust.meta_pages
    image_urls = [page.image_urls[size] for page in allPages]
    return image_urls

def download_images(image_urls, save_dir):
    # if folder already exists and has files, do not download again
    if os.path.exists(save_dir) and any(os.path.isfile(os.path.join(save_dir, f)) for f in os.listdir(save_dir)):
        print(f"Folder {save_dir} already exists and has files. Skipping download.")
        return

    os.makedirs(save_dir, exist_ok=True)
    for url in image_urls:
        api.download(url, path=save_dir)


def refresh_token_if_needed():
    global last_refresh_token_time
    global token

    current_time = datetime.now()
    if last_refresh_token_time is None or current_time - last_refresh_token_time > timedelta(hours=24):
        print("Refreshing token...")
        token = refresh_and_get_token(token)
        last_refresh_token_time = datetime.now()

def clean_download_folder():
    now = datetime.now()
    retention_period = timedelta(days=7)  # retention period is 7 days

    if not os.path.exists(DOWNLOAD_FOLDER):
        print("Download folder does not exist.")
        return

    for item in os.listdir(DOWNLOAD_FOLDER):
        item_path = os.path.join(DOWNLOAD_FOLDER, item)

        # check if the item is older than the retention period, based on its modified time
        item_modified_time = datetime.fromtimestamp(os.path.getmtime(item_path))
        if now - item_modified_time > retention_period:
            if os.path.isfile(item_path):
                print(f"Deleting old file: {item_path}")
                os.remove(item_path)
            elif os.path.isdir(item_path):
                print(f"Deleting folder and its contents: {item_path}")
                shutil.rmtree(item_path)

scheduler = BackgroundScheduler()
scheduler.add_job(func=clean_download_folder, trigger="interval", days=1)  # run every day
scheduler.start()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/fetch", methods=["POST"])
def fetch_images():
    refresh_token_if_needed()
    api.auth(refresh_token=token)

    # artworkId = 125609357
    artworkId = request.json.get("artworkId")
    imageQuality = "original" if request.json.get("selectOriginalImage") else "large"
    save_dir = f"./downloads/{str(artworkId)}/{str(imageQuality)}"

    image_urls = fetch_image_urls(artworkId, imageQuality)

    if not image_urls or len(image_urls) == 0:
        return jsonify({"error": f"Could not find images of artwork {artworkId}"}), 404

    download_images(image_urls, save_dir)
    return jsonify({"message": f"Downloaded {len(image_urls)} images of artwork {artworkId}."})

@app.route("/download/<artworkId>")
def download_folder(artworkId):
    imageQuality = request.args.get("imageQuality", "original").lower()

    zip_path = "./downloads/zips"
    os.makedirs(zip_path, exist_ok=True)

    folder_path = f"./downloads/{artworkId}/{imageQuality}"
    if not os.path.exists(folder_path):
        return jsonify({"error": f"Folder {folder_path} does not exist."}), 404
    
    zip_file_path = f"{zip_path}/pixiv_{artworkId}_{imageQuality}.zip"
    # if the zip file already exists, return it
    if os.path.exists(zip_file_path):
        print(f"Zip file {zip_file_path} already exists. Returning it.")
        return send_file(zip_file_path, as_attachment=True)
    
    # otherwise, create the zip file
    with zipfile.ZipFile(zip_file_path, "w") as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zipf.write(file_path, arcname)
    
    return send_file(zip_file_path, as_attachment=True)

if __name__ == "__main__":
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    app.run(host="0.0.0.0", port=5000)
