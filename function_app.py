import logging
import azure.functions as func
from simple_priority_handler import set_priorities
app = func.FunctionApp()

@app.schedule(schedule="0 1 * * * *", arg_name="myTimer", run_on_startup=True, use_monitor=False) 
def priority_job(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due!')
    logging.info('Python timer trigger function executed.')
    set_priorities()

