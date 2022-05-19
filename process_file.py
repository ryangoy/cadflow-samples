import requests
import os
import time

API_URL = 'https://api2.cadflow.ai'
UPLOAD_ENDPOINT = API_URL +'/upload-file'
POLL_ENDPOINT = API_URL + '/poll-file/'
POLL_INTERVAL = 15 # Time between poll calls in seconds

# Retrieves token, valid for 24 hours
def get_token(client_id, refresh_token):
    print('Fetching token...')
    res = requests.post("https://cadflow.auth0.com/oauth/token", 
        headers = {
            'content-type': 'application/x-www-form-urlencoded'},
        data = {
            'grant_type': 'refresh_token',
            'client_id': client_id,
            'refresh_token': refresh_token,
            'audience': 'https://cadflow.ai/api'
        }
    ) 
    if res.status_code != 200:
        print("Invalid credentials. Exiting..")
        exit()

    return res.json()['access_token']

# Post request requires cid (customer id), filename, and prescription
def process_file(filename, token, practice_id='abc123', prescription_id='def456789', abr=True, basing=True, trim=True):
    
    assert type(filename) == str and filename.endswith('.stl')

    header = {'Authorization': f'Bearer {token}'}
    print('Upload prescription...')
    # POST prescription and retrieve upload and download urls
    ul_resp = requests.put(UPLOAD_ENDPOINT, headers=header, json={
            "filename": os.path.basename(filename),
            "practice_id": practice_id,
            "prescription_id": prescription_id,
            "prescription": {
                "abr": abr,
                "base": basing,
                "trim": trim,
                "params": {
                    "trim_horseshoe": True,
                    "trim_margin": 3.0,
                    "base_margin": 2.0,
                    "base_label": "Your Label Here",
                    "base_z_axis_aligned": True,
                }
            }})

    if ul_resp.status_code != 200:
        print(ul_resp.text)
        return

    # Upload .stl file to s3 using a pre-signed url
    print(f'Uploading file with fid {ul_resp.json()["fid"]}...')
    os.system(f"curl -T {filename} -H 'Content-Type: model/stl' '{ul_resp.json()['url']}'")

    # Poll for processed file
    print("Beginning polling, waiting for file to become available for download.")
    new_fname = filename.split('.')[0] + '_processed.stl'

    while True:
        # Poll with fid as a path parameter
        poll_resp = requests.post(POLL_ENDPOINT + str(ul_resp.json()['fid']), headers=header)
        print(f'Poll received status {poll_resp.status_code} with message {poll_resp.text}')

        if poll_resp.status_code == 200:
            # Download processed file
            os.system(f"curl -o {new_fname} '{poll_resp.json()['url']}'")
            print(f'Processing finished, downloaded to {new_fname}.')
            if 'trimpath_url' in poll_resp.json():
                os.system(f"curl -o {new_trimpath_fname} '{poll_resp.json()['trimpath_url']}'")
                print(f'Trim path, downloaded to {new_trimpath_fname}.')
            break
        elif poll_resp.status_code != 503 and poll_resp.status_code >= 400:
            print('Exiting.')
            break
        else:
            time.sleep(POLL_INTERVAL)


if __name__ == '__main__':

    client_id = #DEFINE
    refresh_token = #DEFINE
                      
    # Retrieve token once every 10 hours
    token = get_token(client_id, refresh_token)
    
    # Call this method any number of times with the same token                  
    process_file(input_file_path, token)
