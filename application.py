import tkinter as tk
from google_play_scraper import app, reviews, reviews_all, Sort
from PIL import Image, ImageTk
from googlesearch import search
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shutil
import re
import os
from tabulate import tabulate
import pickle
import nltk
nltk.download('stopwords')




def getDetails(url):
  app_id=url.split('?')[1].split('&')[0][3:]
  app_attr=app(app_id)
  x=str(app_attr['title'])+'\nAPP ID: '+str(app_id)+'\nRATING: '+str(app_attr['score'])+'\nTOTAL RATINGS: '+str(app_attr['ratings'])+'\nTOTAL REVIEWS: '+str(app_attr['reviews'])+'\nREVIEWS ANALYZED: '+str(r)
  return x


def wrt(name,content):  
    f=open(name, 'w+')
    f.write(content)
    f.close()

    
def red(name):
    f = open(name,"r") 
    x = f.read()
    f.close()   
    return x


def getReviews(url,n=10):
  global r
  r=str(n)
  app_id=url.split('?')[1].split('&')[0][3:]
  app_attr=app(app_id)
  if n=='all': n=app_attr['ratings']
  n=int(n)
  app_reviews = reviews(app_id, country='us',
                        sort=Sort.MOST_RELEVANT,count=n)
  
  df = pd.DataFrame(app_reviews[0]).iloc[:,3:5]
  df.rename(columns = {'content':'REVIEW', 
                       'score':'RATING'}, inplace = True)
  return(df)


def cleanDf(df,col):
  reviews=[]
  for row in df[col]:
     row=re.sub('[^a-z]', ' ', row.lower())
     stopWords = nltk.corpus.stopwords.words('english')
     stopWords.remove('not')
     row=row.split()
     row = [nltk.stem.porter.PorterStemmer().stem(word) for word in row if not word in set(stopWords)]
     row = ' '.join(row)
     reviews.append(row)
  df[col]=reviews
  return df
  

def bagOfWords(x):
  from sklearn.feature_extraction.text import CountVectorizer
  cv = CountVectorizer(max_features=13500)
  x = cv.fit_transform(x).toarray()
  n=len(x[0])
  l=[]
  for i in x:
      l.append(list(i)+[0 for i in range(13500-n)])
  del x    
  return(np.array(l))


def getVisualizations(df,path):  
  x =df['SENTIMENT'];y =df['RATING']
  plt.yticks(np.arange(1,6,1))  
  plt.xlabel("Sentiments",size=15)
  plt.ylabel("Ratings",size=15)
  plt.bar(x, y)
  plt.grid(axis='y')
  plt.savefig(path+'/SentimentvsRating.png',dpi=100)
  plt.show()
  
  data = df['SENTIMENT'].value_counts()
  x = list(data);y = list(data.index)
  circle=plt.Circle( (0,0), 0.7, color='white')
  plt.gcf().gca().add_artist(circle)
  plt.pie(x,autopct='%1.0f%%')
  plt.title("Sentiment Analysis",size=15,loc='left')
  plt.legend(labels=y,bbox_to_anchor=(1, 0.8))
  plt.savefig(path+'/SentimentAnalysis.png',dpi=100)
  plt.show()
  
  data = df['RATING'].value_counts()
  x = list(data);y = list(data.index)
  plt.pie(x,autopct='%1.0f%%')
  plt.title("Rating Analysis",size=15,loc='left')
  plt.legend(labels=y,bbox_to_anchor=(1, .8))
  plt.savefig(path+'/RatingAnalysis.png',dpi=100)  
  plt.show()
  

def getInsights(df):
  c32=df.loc[(df['RATING'] >=3) & (df['SENTIMENT'] == 2)].shape[0]
  c31=df.loc[(df['RATING'] >=3) & (df['SENTIMENT'] == 1)].shape[0]
  c30=df.loc[(df['RATING'] >=3) & (df['SENTIMENT'] == 0)].shape[0]
  t=int(df.shape[0])

  a='.> '+str(c32*100//t)+'% of the Positive reviews have ratings greater than 2'
  b='.> '+str(c31*100//t)+'% of the Neutral reviews have ratings greater than 2'
  c='.> '+str(c30*100//t)+'% of the Negative reviews have ratings greater than 2'
  return a+'\n'+b+'\n'+c+'\n\n' 


def displayTable():  
    global e
    e=0
    try:
            text = inp.get(1.0, "end-1c")
            num = inp2.get(1.0, "end-1c")
            x=list(search('playstore '+text ,num_results=0))[0]
            
            df=getReviews(x,num)
            df2=df.copy(deep=True)
            df=cleanDf(df,'REVIEW')
            
            model = pickle.load(open('model.pkl','rb'))
            reviews=bagOfWords(df['REVIEW'])
            sentiments=model.predict(reviews)
            df['SENTIMENT']=df2['SENTIMENT']=sentiments
            df2['SENTIMENT'].replace({0: 'Negative', 
                                          1: 'Neutral', 
                                          2: 'Positive'}, inplace=True)
            
            app_attr=app(x.split('?')[1].split('&')[0][3:])
            name=str(app_attr['title']).split()[0]
            
            global pth
            pth='Resources/'+name
            if os.path.exists(pth):
                 shutil.rmtree(os.path.join(pth)) 
            os.makedirs(pth)
            
            df2.to_csv(pth+'/reviews.csv',index=False)
            wrt(pth+'/details.txt',getDetails(x))
            wrt(pth+'/insights.txt',getInsights(df)+'File location:- '+os.path.abspath(pth))  
            
            df2=pd.read_csv(pth+'/reviews.csv', index_col=False) 
            df2['REVIEW']= [ i[:30]+'...' for i in df2['REVIEW'] ]
            
            df2=df2[['SENTIMENT','RATING','REVIEW']]
            df2.index.name = 'I'
            getVisualizations(df2, 'Resources/'+name)
            op=tabulate(df2.sample(5), headers='keys')
            
    except: op='Please Try Again!'; e=1
    tk.Label(root, 
             text=op,bg='white',
             font=("Arial", 15),width = 50,height=7,
             justify='left').place(x=60, y=500)    
                     
    
def displayDetails(): 
    op=red(pth+"/details.txt")
    if e==1:op='Exception Occured!'
    tk.Label(root, text=op,bg='white',
             font=("Arial", 15),width=33,height=6,
             justify='left').place(x=250, y=300)
    
    
def displayInsights():  
    op=red(pth+"/insights.txt")
    if e==1:op='Error!'
    tk.Label(root, text=op,bg='white',
             width = 50,height=5,justify='left',
             font=("Arial", 15)).place(x=60, y=725)    

    
def displayVisualizations(): 
    if e==1:
        tk.Label(root, text="Insufficient Information!",font=("Arial", 15),
                 width = 66,height=13).place(x=775, y=225) 
        tk.Label(root, text="Insufficient Information!",
                 font=("Arial", 15),width = 32,height=12).place(x=775, y=550) 
        tk.Label(root, text="Insufficient Information!",
                 font=("Arial", 15),
                 width = 32,height=12).place(x=1150, y=550) 
    else:
        img= Image.open(pth+'/SentimentvsRating.png').resize((725,300),
                                                             Image.Resampling.LANCZOS)
        tkimage = ImageTk.PhotoImage(img)
        p=tk.Label(image = tkimage)
        p.place(x=775, y=225)
        p.photo=tkimage
        
        img= Image.open(pth+'/SentimentAnalysis.png').resize((350,275),
                                                             Image.Resampling.LANCZOS)
        tkimage = ImageTk.PhotoImage(img)
        p=tk.Label(image = tkimage)
        p.place(x=775, y=550)
        p.photo=tkimage
        
        img= Image.open(pth+'/RatingAnalysis.png').resize((350,275),
                                                             Image.Resampling.LANCZOS)
        tkimage = ImageTk.PhotoImage(img)
        p=tk.Label(image = tkimage)
        p.place(x=1150, y=550)
        p.photo=tkimage




root= tk.Tk()
root.title("ARA") 
root.attributes('-fullscreen',True)

image = Image.open("Images/cover.png")
reimage= image.resize((1920,1080),Image.Resampling.LANCZOS)
img = ImageTk.PhotoImage(reimage) 
tk.Label(image=img).place(x=0,y=0)

inp=tk.Text(root,height = 1,width = 13,font=("Kino MT", 20))
inp.place(x=280,y=180)
inp2=tk.Text(root,height = 1,width = 13,font=("Kino MT", 20))
inp2.place(x=280,y=230)


tk.Label(root, text = "Enter App Name:", font=("Bauhaus 93", 15),
         fg='red',bg='black').place(x=60,y=180)
tk.Label(root, text = "No. of Reviews (min. 5):", font=("Bauhaus 93", 15),
         fg='red',bg='black').place(x=60,y=230)
tk.Label(root, text = "App Details:", font=("Bauhaus 93", 25),
         fg='red',bg='black').place(x=60,y=325)
tk.Label(root, text = "Sample Table Generated:", font=("Bauhaus 93", 25),
         fg='red',bg='black').place(x=60,y=450)
tk.Label(root, text = "Insights:", font=("Bauhaus 93", 25),
         fg='red',bg='black').place(x=60,y=675)
tk.Label(root, text = "Visualizations:", font=("Bauhaus 93", 25),
         fg='red',bg='black').place(x=762.5,y=180)


tk.Label(root, text="Information extracted from playstore",
         font=("Arial", 15),width=33,height=6).place(x=250, y=300)
tk.Label(root,text="Randomly selected 5 rows from the table ",font=("Arial 93", 15),width = 50,height=7).place(x=60, y=500)
tk.Label(root, text="Information genereated from the table",
         width = 50,height=5,font=("Arial", 15)).place(x=60, y=725) 
tk.Label(root, text="Sentiment vs Rating Graph",font=("Arial", 15),
         width = 66,height=13).place(x=775, y=225) 
tk.Label(root, text="Sentiment Analysis Graph",
         font=("Arial", 15),width = 32,height=12).place(x=775, y=550) 
tk.Label(root, text="Rating Analysis Graph",
         font=("Arial", 15),
         width = 32,height=12).place(x=1150, y=550) 


analyze= tk.PhotoImage(file = r"Images/Analyze.png")
tk.Button(text='Submit',image=analyze ,command=lambda:[displayTable(),
                                         displayDetails(),
                                         displayInsights(),
                                         displayVisualizations()]).place(x=500, y=200)

close = tk.PhotoImage(file = r"Images/close.png")
tk.Button(root, text = "close",image = close,
                            command = root.destroy).place(x=0,y=0) 

root.mainloop()
