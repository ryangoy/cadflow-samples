import requests
import os
import time

API_URL = 'https://m1226tf1be.execute-api.us-west-1.amazonaws.com'
UPLOAD_ENDPOINT = API_URL +'/prod/upload-file'
POLL_ENDPOINT = API_URL + '/prod/poll-file/'
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
    return res.json()['access_token']

# Post request requires cid (customer id), filename, and prescription
def process_file(user_id, filename, token, abr=True, basing=False, trim=False):
    
    assert type(filename) == str and filename.endswith('.stl')
    assert type(user_id) == str
    assert type(abr) == bool and not basing and not trim # basing and trim are turned off currently

    header = {'Authorization': f'Bearer {token}'}

    # POST prescription and retrieve upload and download urls
    ul_resp = requests.put(UPLOAD_ENDPOINT, headers=header, json={
            "cid": user_id,
            "filename": os.path.basename(filename),
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
    os.system(f"curl -T {filename} '{ul_resp.json()['url']}'")

    # Poll for processed file
    print("Beginning polling, waiting for file to become available for download.")
    new_fname = os.path.basename(filename).split('.')[0] + '_processed.stl'

    while True:
        # Poll with fid as a path parameter
        poll_resp = requests.get(POLL_ENDPOINT + str(ul_resp.json()['fid']), headers=header)
        print(f'Poll received status {poll_resp.status_code} with message {poll_resp.text}')

        if poll_resp.status_code == 200:
            # Download processed file
            os.system(f"curl -o {new_fname} '{poll_resp.json()['url']}'")
            break
        elif poll_resp.status_code == 400:
            print('Exiting.')
            break
        else:
            time.sleep(POLL_INTERVAL)
    print(f'Processing finished, downloaded to {new_fname}.')


if __name__ == '__main__':

    token = get_token('S9qR2BX2HfGR2u799mgnhXtN46DOxqQL', 'WwJfkX05vCjpT41MoEr-C9C_InrlGKxrzMyMnV6Spsh1Ms3BlOMNrlgffHvbSpsM')
    process_file('google-oauth2|115005983988899165588', '/home/ryan/Desktop/landing_removed.stl', token)
