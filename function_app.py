import logging
import azure.functions as func
from priority_handler import set_priorities
app = func.FunctionApp()

@app.schedule(schedule="10 * * * * *", arg_name="myTimer", run_on_startup=True, use_monitor=False) 
def priority_job(myTimer: func.TimerRequest) -> None:
    if myTimer.past_due:
        logging.info('The timer is past due!')
    set_priorities()

if __name__ == "__main__":
    set_priorities()
