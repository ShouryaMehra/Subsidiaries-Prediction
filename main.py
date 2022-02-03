# Load libraries
from bs4 import BeautifulSoup
import requests
import urllib 
from fake_useragent import UserAgent
import re
from flask import Flask,jsonify,request,send_file
import unidecode
from re import search
from collections import defaultdict
import spacy
import os
from dotenv import load_dotenv
import json

# load spacy base model
nlp = spacy.load("en_core_web_md")

# convert multidimension list to one dimension
def Extract(lst): 
    tscores = [x for x in lst if x != []]
    return [item[0] for item in tscores]  

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
# set env for secret key
load_dotenv()

secret_id = os.getenv('AI_SERVICE_SECRET_KEY')

def check_for_secret_id(request_data):    
    try:
        if 'secret_id' not in request_data.keys():
            return False, "Secret Key Not Found."
        
        else:
            if request_data['secret_id'] == secret_id:
                return True, "Secret Key Matched"
            else:
                return False, "Secret Key Does Not Match. Incorrect Key."
    except Exception as e:
        message = "Error while checking secret id: " + str(e)
        return False,message

@app.route('/subsidiaries_prd',methods=['POST'])  #main function
def main():
    params = request.get_json()
    input_query=params["data"]
    key = params['secret_id']

    request_data = {'secret_id' : key}
    secret_id_status,secret_id_message = check_for_secret_id(request_data)
    print ("Secret ID Check: ", secret_id_status,secret_id_message)
    if not secret_id_status:
        return jsonify({'message':"Secret Key Does Not Match. Incorrect Key.",
                        'success':False}) 
    else:
        val = input_query[0]['query']
        outcome=[]
        temp1 = []
        linkls2 = []
        tempList = []
        tempList2 = []
        # extract subsidiaries from wikipedia
        val = ' '.join(word[0].upper() + word[1:] for word in val.split())
        try:
            url1 = "https://en.wikipedia.org/wiki/List_of_mergers_and_acquisitions_by_" + val
            url2 = "https://en.wikipedia.org/wiki/List_of_acquisitions_by_" + val
            url_list = [url1,url2]  
            for i in url_list:
                r = requests.get(i)
                if r.status_code == 200:  #  check permission
                    soup = BeautifulSoup(r.content ,'html.parser')
                    right_table = soup.find('table',{"class":'wikitable sortable'})
                    header = [th.text.strip() for th in right_table.find_all('th')]  # scrape data
                    
                    # check for category
                    comp = 'Company'
                    comp2 = 'Acquired company'
                    # get title name
                    for i in range(0, len(header)):   
                        if header[i] == comp: 
                            res = None
                            res = i + 1
                            #  print('first title position found')
                            resp= "yes"
                            break
                        else:
                            if header[i] == comp2:
                                res = None
                                res = i + 1
                                #   print('second title position found')
                                resp= "yes"
                                break   
                            else:
                                #  print(i,"first title position not found")
                                outcome.clear()
            if resp == "yes":            
                for row in right_table.find_all("tr"):
                    cells  = row.find_all('td')
                    if len(cells)>0:
                        temp1.append(cells[res-1].find(text=True).strip())
                outcome = temp1        
                
            else:
                outcome.clear()            
        except:
            # extract subsidiaries from sec.gov
            try:
                linkls= []
                linkls2 = []
                tempList = []
                tempList2 = []
                outcome=[]
                query = val.replace(' ','+')
                query = urllib.parse.quote_plus(query) 
                number_result = 7 # iterate 7 links to find correct link
                
                ua = UserAgent()
                # get links from google search
                google_url = "https://www.google.com/search?q=" + query +'+subsidiaries+sec+gov'+ "&num=" + str(number_result)  
                response = requests.get(google_url, {"User-Agent": ua.random})  
                soup = BeautifulSoup(response.text, "html.parser") 
                
                result_div = soup.find_all('div', attrs = {'class': 'ZINbbc'}) 
                
                for r in result_div:
                    try:
                        link = r.find('a', href = True)
                        title = r.find('div', attrs={'class':'vvjwJb'}).get_text()
                        
                        if link != '': 
                            links = link['href']
                            linkls.append(links)
                    # Next loop if one element is not present
                    except:
                        continue
                    
                # search link by key word "dex"    
                for i in linkls:
                    if search("dex",i):
                        linkls2.append(i) 
                        
                # clean link and get data from perticular link        
                if len(linkls2) != 0:   
                    link = linkls2[0].replace('/url?q=','')
                    head, sep, tail = link.partition('&') 
                    rowls = []
                    r = requests.get(head) 
                    soup = BeautifulSoup(r.content ,'html.parser')   
                    
                    # extract data from html code
                    table = soup.find_all('table')
                    for i in table:
                        tbrow = i.find_all('tr')
                        for trow in tbrow:
                            td = trow.find_all('td')
                            row = [i.text for i in td]
                            rowls.append(row)
                    
                    list = []
                    # dimension reduction
                    list.append(Extract(rowls))
                    
                    # clean extracted data 
                    for sublist in list:
                        for item in sublist:
                            item = item.replace('\n'," ")      
                            item = unidecode.unidecode(item)
                            item =''.join([i for i in item if not i.isdigit()])
                            item = re.sub(r'\b\w{1,1}\b', '', item)
                            item = re.sub(' +', ' ', item)
                            item = re.sub('[^a-zA-Z0-9 \d\s]+', '', item).strip()        
                            if item != "Name" and item != "" and item !="Legal Name" and item != "Entity" and item !="Name of Subsidiary" and item != "Subsidiaries" and item != "NAME OF SUBSIDIARY" and item !="Subsidiary Name" and item !="SUBSIDIARIES OF THE PARENT" and item !="Name of subsidiaries" and item !="Country Name" and item !="Company Name" and len(item) < 70 and item.find("subsidiary") <= 0 and item.find("Subsidiary"):
                                tempList.append(item)      
                            
                    # set probability range 80% using spacy and find only 'ORG' tag data        
                    with nlp.disable_pipes('ner'):
                        doc = nlp(str(tempList))
                        
                    threshold = 0.8 # set threshold range
                    beams = nlp.entity.beam_parse([ doc ], beam_width = 16, beam_density = 0.0001)
                    entity_scores = defaultdict(float)    
                    for beam in beams:
                        for score, ents in nlp.entity.moves.get_beam_parses(beam):
                            for start, end, label in ents:
                                entity_scores[(start, end, label)] += score             
                    for key in entity_scores:
                        start, end, label = key
                        score = entity_scores[key]
                        if ( score > threshold):
                            if label == 'ORG': # set tag to find
                                if search("'",str(doc[start:end])):
                                    temp = str(doc[start:end]).replace("'","") 
                                    tempList2.append(temp)
                                else:
                                    tempList2.append(str(doc[start:end]))
                    outcome = tempList2        
            except:
                # if error occure then clear list
                outcome.clear()
        
        if len(outcome) == 0:
            try:
                outcome = []
                # search company subsidiaries
                val = val.replace(" ","+")
                url="https://www.google.com/search?q="+ val + "+subsidiaries"
                r = requests.get(url)
                html = r.content
                soup = BeautifulSoup(html ,'html.parser')
                
                # get all subsideries name from google search
                sp = soup.find(class_="ZINbbc xpd O9g5cc uUPGi") # call unique class to select only first section of subsideries
                for link in sp.find_all('a',{'class':"tHmfQe"}):
                    # clean data
                    x=link.get('href').split("stick")[0].split("q=")[1].replace("+"," ")[:-1]
                    # set length of companies for clean data
                    if len(x) < 70:
                        outcome.append(x) 

                if len(outcome) == 0:
                    outcome = []
                    for link in sp.find_all('a',{'class':"BVG0Nb"}):
                        # clean data
                        x=link.get('href').split("stick")[0].split("q=")[1].replace("+"," ")[:-1]
                        # set length of companies for clean data
                        if len(x)< 70:
                            outcome.append(x) 
            except:
                # clear list if it error occure 
                outcome.clear()            
            
                
        # send message when list is empty        
        if len(outcome)==0:
            outcome.append("List is Empty")     
        
        dict1 = {'Subsidiaries':outcome}

    return dict1

if __name__ == '__main__':
    app.run()