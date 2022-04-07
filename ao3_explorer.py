import streamlit as st
import pandas as pd
import numpy as np
import os
from google.cloud import storage
from google.cloud import bigquery
from google.oauth2 import service_account
import re
from bs4 import BeautifulSoup, NavigableString
import urllib.request


credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(credentials=credentials)

st.markdown("# AO3 Playground")

st.sidebar.markdown("## 工具栏")

@st.cache(persist=True, show_spinner=True, allow_output_mutation=True)

def load_data():
    query = "SELECT * FROM `cse6242-343901.ggad.table1`"
    df = client.query(query).to_dataframe()
    return df

data_load_state = st.text('Loading dataset...')
df = load_data()
data_load_state.text('Loading dataset...Completed!')

stats = pd.read_csv("GGAD_stats.csv", index_col=0)
full_df = df.merge(stats.loc[:,stats.columns!='Date_published'], on='ID', how='inner')

st.text('Step 1')
lang = st.selectbox("选择一种语言", index=0, options=sorted(list(set(full_df.Language.to_list()))))
st.text('Step 2')
author = st.selectbox("选择一位作者", index=0, options=sorted(list(set(full_df.loc[full_df.Language==lang].Author.to_list()))))

def open_fic(work_id):
    url = 'https://archiveofourown.org' + work_id + '?view_adult=true&show_comments=true&view_full_work=true'
    req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req)
    print('Successfully opened fiction:', url)
    bs = BeautifulSoup(resp, 'lxml')
    return bs

titles = []
summaries = []
for idx, row in full_df.loc[(full_df.Author==author)&(full_df.Language==lang)].iterrows():
    titles.append(row['Title'])
    summaries.append(row['Summary'])
    if st.checkbox(row['Title']):
        st.markdown(row['Summary'])
        st.write(f"https://archiveofourown.org/works/{row['ID']}/")
        get_fic_btn = st.button('Get FanFic!', key=idx)
        if get_fic_btn:
            bs = open_fic(f"/works/{row['ID']}")
            chapters = bs.find('div', {'id':'chapters'})
            texts = chapters.find_all('p')
            content = ' \n '.join([t.text for t in texts])
            content = row['Content'].replace('\n', ' \n\n\n ').replace('\xa0', ' \n\n\n ').replace('\u3000', ' \n\n\n ')
            st.write(re.sub("~+", " \* ", str(content)))

