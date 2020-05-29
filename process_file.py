import requests
import os
import time

API_URL = 'https://gz2pve4omi.execute-api.us-west-1.amazonaws.com'
UPLOAD_ENDPOINT = API_URL +'/dev/uploadfile'
POLL_ENDPOINT = API_URL + '/dev/pollfile/'
POLL_INTERVAL = 15 # Time between poll calls in seconds

# Retrieves token, valid for 24 hours
def get_token(m2m_id, m2m_secret):
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
            }}).json()

    # Upload .stl file to s3 using a pre-signed url
    print(ul_resp)
    os.system(f"curl -T {filename} '{ul_resp['url']}'")
    print('Finished uploading file')

    # Poll for processed file
    print("Beginning polling, waiting for file to become available for download.")
    new_fname = os.path.basename(filename).split('.')[0] + '_processed.stl'
    while True:
        poll_resp = requests.get(POLL_ENDPOINT + str(ul_resp['fid']), headers=header)
        print(poll_resp)
        if poll_resp.status_code == 200:
            os.system(f"curl -o {new_fname} '{poll_resp.json()['url']}'")
            break
        else:
            time.sleep(POLL_INTERVAL)
    print(f'Processing finished, downloaded to {new_fname}.')


if __name__ == '__main__':

    token = get_token('cXYJtY55DI5KN03cDxv540u0vg08tkyg', 'mheDMDKX4nmq-MfTNdLOrAsUwrSFe2gWRc_HNVpdbnqX-9RZQZ23Fg8fM-qS2oXm')
    process_file('google-oauth2|115005983988899165588', '/home/ryan/Desktop/input.stl', token)
