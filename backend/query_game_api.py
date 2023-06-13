import json
import urllib3
import logging

# setup requests pool
retryAmount = 3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
retries = urllib3.Retry(connect=retryAmount, read=retryAmount, redirect=2, status=retryAmount, status_forcelist=[502, 503])
http = urllib3.PoolManager(retries=retries)

def make_json_request(url, token, attempt = 0):
    response = None
    jsonDat = None
    try:
        response = http.request(
            "GET",
            url,
            headers={
                "Host": "game-api.skymavis.com",
                "User-Agent": "UnityPlayer/2019.4.28f1 (UnityWebRequest/1.0, libcurl/7.52.0-DEV)",
                "Accept": "*/*",
                "Accept-Encoding": "identity",
                "Authorization": 'Bearer ' + token,
                "X-Unity-Version": "2019.4.28f1"
            }
        )

        jsonDat = json.loads(response.data.decode('utf8'))  # .decode('utf8')
        succ = False
        if 'success' in jsonDat:
            succ = jsonDat['success']

        if 'story_id' in jsonDat:
            succ = True

        if not succ:
            if 'details' in jsonDat and len(jsonDat['details']) > 0:
                if 'code' in jsonDat:
                    logging.error(f"API call failed in makeJsonRequest for: {url}, {jsonDat['code']}, attempt {attempt}")
                else:
                    logging.error(f"API call failed in makeJsonRequest for: {url}, {jsonDat['details'][0]}, attempt {attempt}")
            else:
                logging.error(f"API call failed in makeJsonRequest for: {url}, attempt {attempt}")

            if attempt < 3:
                return make_json_request(url, token, attempt + 1)
            else:
                return None

    except Exception as e:
        logging.error(f"Exception in makeJsonRequest for: {url}, attempt {attempt}")
        logging.error(response.data.decode('utf8'))
        if attempt < 3:
            return make_json_request(url, token, attempt + 1)
        else:
            return None

    return jsonDat
