import requests
import os
import time

API_URL = 'https://api.cadflow.ai'
UPLOAD_ENDPOINT = API_URL +'/upload-file'
POLL_ENDPOINT = API_URL + '/poll-file/'
POLL_INTERVAL = 15 # Time between poll calls in seconds

# Retrieves token, valid for 24 hours
def get_token(m2m_id, m2m_secret):
    print('Fetching token...')
    res = requests.post("https://cadflow.auth0.com/oauth/token", 
        headers = {
            'content-type': 'application/x-www-form-urlencoded'},
        data = {
            'grant_type': 'client_credentials',
            'client_id': m2m_id,
            'client_secret': m2m_secret,
            'audience': 'https://cadflow.ai/api'
        }
    ) 
    if res.status_code != 200:
        print("Invalid credentials. Exiting..")
        exit()

    return res.json()['access_token']

# Post request requires cid (customer id), filename, and prescription
def process_file(filename, token, practice_id='abc123', prescription_id='def456789', abr=True, basing=False, trim=False):
    
    assert type(filename) == str and filename.endswith('.stl')
    assert type(abr) == bool and not basing and not trim # basing and trim are turned off currently

    header = {'Authorization': f'Bearer {token}'}
    print('Upload prescription...')
    # POST prescription and retrieve upload and download urls
    ul_resp = requests.put(UPLOAD_ENDPOINT, headers=header, json={
            "filename": os.path.basename(filename),
            "practice_id": practice_id,
            "prescription_id": prescription_id,
            "prescription": {
                "abr": abr,
                "basing": basing,
                "trim": trim
            }})

    if ul_resp.status_code != 200:
        print(ul_resp.text)
        return

    # Upload .stl file to s3 using a pre-signed url
    print('Uploading file...')
    os.system(f"curl -T {filename} -H 'Content-Type: model/stl' '{ul_resp.json()['url']}'")

    # Poll for processed file
    print("Beginning polling, waiting for file to become available for download.")
    new_fname = os.path.basename(filename).split('.')[0] + '_processed.stl'

    while True:
        # Poll with fid as a path parameter
        poll_resp = requests.post(POLL_ENDPOINT + str(ul_resp.json()['fid']), headers=header)
        print(f'Poll received status {poll_resp.status_code} with message {poll_resp.text}')

        if poll_resp.status_code == 200:
            # Download processed file
            os.system(f"curl -o {new_fname} '{poll_resp.json()['url']}'")
            print(f'Processing finished, downloaded to {new_fname}.')
            break
        elif poll_resp.status_code == 400:
            print('Exiting.')
            break
        else:
            time.sleep(POLL_INTERVAL)


if __name__ == '__main__':

    public_key = #DEFINE
    private_key = #DEFINE
    token = #DEFINE
    token = get_token(public_key, private_key)
    process_file(input_file_path, token)
