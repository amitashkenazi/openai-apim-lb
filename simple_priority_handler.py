import os
import requests
import logging
import json
import time


def sample_region(url):
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
    response = requests.request("POST", f"{os.environ.get('API_URL')}/chat/completions", headers=headers, data=payload)
    return response
    

def get_backends(url):
    headers = {
        'Ocp-Apim-Subscription-Key': os.environ["API_SUBSCRIPTION_KEY"],
        'Content-Type': 'application/json'
    }
    get_backends_url = f"{url}/get_backends"    
    response = requests.request("GET", get_backends_url, headers=headers, data="")
    logging.info("found the following backends:")
    for backend in json.loads(response.text):
        logging.info(backend['url'])
    return  json.loads(response.text)

def get_response_time(loop_interval, loops_count):
    response_times = {}
    backends = get_backends(os.environ.get('API_URL'))
    logging.info("calculate response time")
    for i in range(loops_count):
        logging.info(f"loop: {i}/{loops_count}")
        for backend in backends:
            logging.info(f"backend: {backend['url']}")
            start_time = time.time()*1000
            res = sample_region(backend['url'])
            logging.info(f"response backend url: {res.headers['x-openai-backendurl']}")
            end_time = time.time()*1000
            logging.info(f"response time: {end_time - start_time}")
            if backend["url"] not in response_times:
                response_times[backend['url']] = []
            response_times[backend['url']].append(end_time - start_time)
        time.sleep(loop_interval)
    return response_times

def change_priority(priorities):
    payload = json.dumps(priorities)
    headers = {
        'Ocp-Apim-Subscription-Key': os.environ["API_SUBSCRIPTION_KEY"],
        'Content-Type': 'application/json'
    }
    response = requests.request("POST", f"{os.environ.get('API_URL')}/set_be_priority", headers=headers, data=payload)
    if response.status_code == 200:
        logging.info("priority changed")


def set_priority(priority_step_ms=500, loop_interval=10, loops_count=6):
    response_time = get_response_time(loop_interval, loops_count)
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
    change_priority(change_priority_dict)
    return average_response_time, change_priority_dict

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
        sph.change_priority(priorities)
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
        mock_change_priority.assert_called_once_with(expected_priorities)
    
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
        mock_change_priority.assert_called_once_with(expected_priorities)
    
    
    @patch('requests.post')
    def test_sample_region(self, mock_post):
        # Setup
        region = 'us-west-1'
        expected_result = 'some expected result'
        mock_post.return_value.json.return_value = expected_result
        os.environ["API_SUBSCRIPTION_KEY"] = '123'

        # Call the function
        actual_result = sph.sample_region(region)



if __name__ == '__main__':
    # init logging with line number in the filw
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
    unittest.main()
    # while True:
    #     average_response_time, change_priority_dict = set_priority(50, 10, 1)
        