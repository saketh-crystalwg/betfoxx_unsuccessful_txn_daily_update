import json
import pandas as pd
import  requests
from requests.auth import HTTPBasicAuth
from sqlalchemy import create_engine
import smtplib,ssl
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import formatdate
from email import encoders
import datetime as dt
from datetime import datetime, timedelta
from openpyxl.styles import Alignment
import sys


def send_mail(send_from, send_to, subject, text, server, port, username='', password='', filename=None):
    msg = MIMEMultipart()
    msg['From'] = send_from
    msg['To'] = ', '.join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    msg.attach(MIMEText(text))

    if filename is not None:
        part = MIMEBase('application', "octet-stream")
        part.set_payload(open(filename, "rb").read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={filename}')
        msg.attach(part)

    smtp = smtplib.SMTP_SSL(server, port)
    smtp.login(username, password)
    smtp.sendmail(send_from, send_to, msg.as_string())
    smtp.quit()


day = 1    

date = datetime.today() - timedelta(days=day)
date_1 = datetime.today() - timedelta(days=day-1)

start_day = datetime(date.year, date.month, date.day, 0, 0, 0)

end_day = datetime(date_1.year, date_1.month, date_1.day, 0, 0, 0)

# Set the time to the start of the day

# Format the datetime object into the desired string format
start_time = start_day.strftime('%Y-%m-%dT%H:%M:%S.000Z')

end_time = end_day.strftime('%Y-%m-%dT%H:%M:%S.000Z')

start_time_1 = start_day.strftime('%Y-%m-%d')

txn_url = 'https://adminwebapi.iqsoftllc.com/api/Main/ApiRequest?TimeZone=0&LanguageId=en'

txn_data = {"Controller":"PaymentSystem",
            "Method":"GetPaymentRequestsPaging",
            "RequestObject":{
                "Controller":"PaymentSystem",
                "Method":"GetPaymentRequestsPaging",
                "SkipCount":0,
                "TakeCount":1000,
                "OrderBy":None,
                "FieldNameToOrderBy":"",
                "Type":2,
                "HasNote":False,
                "FromDate":start_time,"ToDate":end_time},
            "UserId":"1780","ApiKey":"betfoxx_api_key"}

txn_response = requests.post(txn_url, json=txn_data)

txn_response_data = txn_response.json()

txn_entities = txn_response_data['ResponseObject']['PaymentRequests']['Entities']

txns = pd.DataFrame(txn_entities)

if txns is not None and txns.shape[0] > 0:
    txns['Status'] = ['Approved' if x == 8 \
                      else 'ApprovedManually' if x == 12 \
                      else 'Cancelled' if x == 2 \
                      else 'CancelPending' if x == 14 \
                      else 'Confirmed' if x == 7 \
                      else 'Declined' if x == 6 \
                      else 'Deleted' if x == 11 \
                      else 'Expired' if x == 13 \
                      else 'Failed' if x == 9 \
                      else 'Frozen' if x == 4 \
                      else 'InProcess' if x == 3 \
                      else 'Pay Pending' if x == 10 \
                      else 'Pending' if x == 1 \
                      else 'Splitted' if x == 15 \
                      else 'Waiting For KYC' if x == 5 \
                      else 'NA' for x in txns['State']]

    filtered_txns = txns[(txns['Status'] != 'Approved') & (txns['Status'] != 'ApprovedManually')][['UserName', 'FirstName', 'LastName', 'Email', 'CreationTime', 'PaymentSystemId', 'Status', 'CurrencyId', 'Amount','ConvertedAmount','Id']]
    filtered_txns['Payment_Method'] = ['InternationalPSP' if x == 326 \
                                       else 'NOWPay' if x == 147 \
                                       else 'XcoinsPayCard' if x == 324 \
                                       else 'XcoinsPayCrypto' if x == 323 \
                                       else 'Others' for x in filtered_txns['PaymentSystemId']]

    failed_txns = filtered_txns[filtered_txns['Status'] !=  'Pending'].reset_index()
    
    failed_comments = pd.DataFrame(columns=['Id', 'Comments'])
    
    if failed_txns is not None and failed_txns.shape[0] > 0:
    
        for i in range (0,failed_txns.shape[0]):
            failed_data = {"Controller":"PaymentSystem",
            "Method":"GetPaymentRequestHistories",
            "RequestObject":{
                "Controller":"PaymentSystem",
                "Method":"GetPaymentRequestHistories",
                "PaymentRequestId":str(failed_txns['Id'][i])},
            "UserId":"1780","ApiKey":"betfoxx_api_key"}
        
            failed_response = requests.post(txn_url, json=failed_data)

            failed_response_data = failed_response.json()

            failed_entities = failed_response_data['ResponseObject'][0]['Comment']
            
            current_row = pd.DataFrame({'Id': [failed_txns['Id'][i]], 'Comments': [failed_entities]})
            
            failed_comments = pd.concat([failed_comments, current_row], ignore_index=True)
        

    result = pd.merge(filtered_txns, failed_comments, how='left', on='Id')
    result_1 =  result[~result['Comments'].str.contains('StatusCode', na=False)]
    result_2 = result[result['Comments'].str.contains('StatusCode', na=False)]
    
    def extract_message(comment):
        if not comment:
            return 'No JSON found'
        try:
        # Find the position of 'message' field
            message_start = comment.find('"message\\":\\"') + len('"message\\":\\"')
            if message_start == -1:
                return 'No message found'
            message_end = comment.find('\\"', message_start)
            if message_end == -1:
                return 'No message found'
        # Extract the message substring
            message = comment[message_start:message_end]
            return message
        except Exception as e:
            return str(e)
        return 'No JSON found'

# Apply the function to the DataFrame
    result_2['Comments'] = result_2['Comments'].apply(extract_message)
    
    result_3 = pd.concat([result_1, result_2], ignore_index=True)
    
    if result_3 is not None and result_3.shape[0] > 0:
        filename = f'Betfoxx_Unsuccessful_Transaction_{start_time_1}.xlsx'
        sub = f'Betfoxx_Unsuccessful_Transaction_{start_time_1}'
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            result_3.reset_index(drop=True).to_excel(writer, sheet_name="Unsuccessful_Txns", index=False)
        with pd.ExcelWriter(filename, engine='openpyxl', mode='a') as writer:
            workbook = writer.book
            worksheet1 = writer.sheets['Unsuccessful_Txns']
            for column in worksheet1.columns:
                max_length = 0
                column_name = column[0].column_letter
                for cell in column:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                adjusted_width = (max_length + 2) * 1.2
                worksheet1.column_dimensions[column_name].width = adjusted_width

            for column in worksheet1.iter_cols(min_col=1, max_col=len(filtered_txns.columns)):
                for cell in column:
                    cell.alignment = Alignment(horizontal='center')

    subject = sub
    body = f"Hi,\n\n Attached contains the details of unsuccessfull transactions  during {start_time_1} for Betfoxx \n\nThanks,\nSaketh"
    sender = "sakethg250@gmail.com"
    recipients = ["sakethg250@gmail.com","alberto@crystalwg.com","shiley@crystalwg.com","saketh@crystalwg.com"]
    password = "xjyb jsdl buri ylqr"

    send_mail(sender, recipients, subject, body, "smtp.gmail.com", 465, sender, password, filename)
else:
    subject = f'Betfoxx_Transaction_Details_{start_time_1}'
    body = f"Hi,\n\nNo failed transactions during {start_time_1} for Betfoxx.\n\nThanks,\nSaketh"
    sender = "sakethg250@gmail.com"
    recipients = ["saketh@crystalwg.com","sakethg250@gmail.com","alberto@crystalwg.com","shiley@crystalwg.com"]
    password = "xjyb jsdl buri ylqr"

    send_mail(sender, recipients, subject, body, "smtp.gmail.com", 465, sender, password)