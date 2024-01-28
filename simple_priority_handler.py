import os
import requests
import logging
import json
import time
from pprint import pprint


api_url = os.environ.get('API_URL', 'https://apim-openai-lb.azure-api.net/set_be_priority')

def sample_region(api_url, url):
    payload = json.dumps({
        "messages": [
            {
            "content": "say yes or no",
            "role": "system",
            "name": "string"
            }
        ],
        "model": "gpt-4"
    })
    headers = {
        'Ocp-Apim-Subscription-Key': os.environ["API_SUBSCRIPTION_KEY"],
        'Content-Type': 'application/json',
        'backendURL': url
    }
    response = requests.request("POST", f"{api_url}/chat/completions", headers=headers, data=payload)
    return response
    

def get_backends(url):
    headers = {
        'Ocp-Apim-Subscription-Key': os.environ["API_SUBSCRIPTION_KEY"],
        'Content-Type': 'application/json'
    }
    get_backends_url = f"{url}/get_backends"    
    response = requests.request("GET", get_backends_url, headers=headers, data="")
    logging.info(f"get_backends response: {response.text}")
    return  json.loads(response.text)

def get_response_time(loop_interval = 10, loops_count = 6):
    response_times = {}
    backends = get_backends(api_url)
    logging.info("calculate response time")
    for i in range(loops_count):
        logging.info(f"loop: {i}/{loops_count}")
        for backend in backends:
            logging.info(f"backend: {backend['url']}")
            start_time = time.time()*1000
            res = sample_region(api_url, backend['url'])
            logging.info(f"response backend url: {res.headers['x-openai-backendurl']}")
            end_time = time.time()*1000
            logging.info(f"response time: {end_time - start_time}")
            if backend["url"] not in response_times:
                response_times[backend['url']] = []
            response_times[backend['url']].append(end_time - start_time)
        time.sleep(loop_interval)
    return response_times

def change_priority(url, priorities):
    print("change priority")
    print(f"priorities: {priorities}")
    payload = json.dumps(priorities)
    headers = {
        'Ocp-Apim-Subscription-Key': os.environ["API_SUBSCRIPTION_KEY"],
        'Content-Type': 'application/json'
    }
    response = requests.request("POST", f"{url}/set_be_priority", headers=headers, data=payload)
    logging.info(response.text)


def set_priority(priority_step_ms=500):
    response_time = get_response_time()
    average_response_time = {}
    logging.info("calculate average response time")
    for backend, response_times in response_time.items():
        average_response_time[backend] = sum(response_times) / len(response_times)
    logging.info(f"average_response_time: {average_response_time}")
    sorted_names = sorted(average_response_time, key=average_response_time.get)
    change_priority_dict = {}
    
    for idx, n in enumerate(sorted_names):
        if idx == 0:
            change_priority_dict[n] = 0
        else:
            if average_response_time[n] > average_response_time[sorted_names[idx-1]] + priority_step_ms:
                change_priority_dict[n] = change_priority_dict[sorted_names[idx-1]] + 1
            else:
                change_priority_dict[n] = change_priority_dict[sorted_names[idx-1]]
        
    logging.info(f"change_priority_dict: {change_priority_dict}")
    change_priority(api_url, change_priority_dict)

import unittest
from unittest.mock import patch
import simple_priority_handler as sph

class TestPriorityHandler(unittest.TestCase):
    @patch('simple_priority_handler.requests.request')
    def test_change_priority(self, mock_request):
        # Setup
        url = 'http://test-url.com'
        priorities = {'backend1': 1, 'backend2': 0}
        expected_payload = '{"backend1": 1, "backend2": 0}'

        # Call the function
        sph.change_priority(url, priorities)
        headers = {
            'Ocp-Apim-Subscription-Key': os.environ["API_SUBSCRIPTION_KEY"],
            'Content-Type': 'application/json'
        }
        # Assert the request was made with the correct parameters
        mock_request.assert_called_once_with("POST", f"{url}/set_be_priority", headers=headers, data=expected_payload)
    
    @patch('simple_priority_handler.get_response_time')
    @patch('simple_priority_handler.change_priority')
    def test_set_priority(self, mock_change_priority, mock_get_response_time):
        # Setup
        mock_get_response_time.return_value = {
            'backend1': [100, 100, 100],
            'backend2': [200, 200, 200]
        }
        expected_priorities = {'backend1': 0, 'backend2': 0}

        # Call the function
        sph.set_priority(priority_step_ms=500)

        # Assert the change_priority function was called with the correct parameters
        mock_change_priority.assert_called_once_with(sph.api_url, expected_priorities)
    
    @patch('simple_priority_handler.get_response_time')
    @patch('simple_priority_handler.change_priority')
    def test_set_priority_2(self, mock_change_priority, mock_get_response_time):
        # Setup
        mock_get_response_time.return_value = {
            'backend1': [100],
            'backend2': [400]
        }
        expected_priorities = {'backend1': 0, 'backend2': 1}

        # Call the function
        sph.set_priority(priority_step_ms=299)

        # Assert the change_priority function was called with the correct parameters
        mock_change_priority.assert_called_once_with(sph.api_url, expected_priorities)
    

if __name__ == '__main__':
    # init logging
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(message)s',
        level=logging.INFO
    )
    unittest.main()

if __name__ == "__main__":
    # enable logging
    logging.basicConfig(
        format='%(asctime)s %(levelname)s %(message)s',
        level=logging.INFO
    )
    # start unittest
    unittest.main()
    # set_priority()