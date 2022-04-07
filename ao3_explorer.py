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


def unique_list(seq):
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]

def pure_comma_separation(list_str, return_list=True):
    r = unique_list([item.strip() for item in list_str.lower().split(",") if item.strip()])
    if return_list:
        return r
    return "|".join(r)

def pure_comma_separation2(list_str, return_list=True):
    r = unique_list([item.strip() for item in list_str.lower().split(",") if item.strip()])
    if return_list:
        return r
    return ",".join(r)

def search_content(phrase, content):
    out = re.findall(fr"{phrase}", content.lower())
    return len(out)

def search_content2(phrase, content):
    words = phrase.split(',')
    out = 0
    for w in words:
        length = len(re.findall(fr"{w}", content.lower()))
        if length > 0:
            out += len(re.findall(fr"{w}", content.lower()))
        if length == 0:
            out = 0
    return out

def open_fic(work_id):
    url = 'https://archiveofourown.org' + work_id + '?view_adult=true&show_comments=true&view_full_work=true'
    req = urllib.request.Request(url)
    resp = urllib.request.urlopen(req)
    print('Successfully opened fiction:', url)
    bs = BeautifulSoup(resp, 'lxml')
    return bs

def get_content(id):
    bs = open_fic(f'/works/{id}')
    chapters = bs.find('div', {'id':'chapters'})
    texts = chapters.find_all('p')
    para = []
    for t in texts:
        para.append('\n'.join(list(t.stripped_strings)))
    content = '\n'.join(para)
    content = content.replace('\n', ' \n\n\n ').replace('\xa0', ' \n\n\n ').replace('\u3000', ' \n\n\n ')
    st.write(re.sub("~+", " \* ", str(content)))

credentials = service_account.Credentials.from_service_account_info(
    st.secrets["gcp_service_account"]
)
client = bigquery.Client(credentials=credentials)

st.markdown("# AO3 Playground -- Under Albus Dumbledore/Gellert Grindelwald Tag")

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

st.sidebar.markdown("## 工具栏")
status = st.sidebar.radio("想怎么挑选？",['按作者筛选','按标题关键词','搜索全文'])
if status == '按作者筛选':
    st.text('Step 1')
    lang = st.selectbox("选择一种语言", index=0, options=sorted(list(set(full_df.Language.to_list()))))
    st.text('Step 2')
    author = st.selectbox("选择一位作者", index=0, options=sorted(list(set(full_df.loc[full_df.Language==lang].Author.to_list()))))


    for idx, row in full_df.loc[(full_df.Author==author)&(full_df.Language==lang)].iterrows():
        with st.expander(row['Title']):
            st.markdown(row['Summary'])
            st.write(f"https://archiveofourown.org/works/{row['ID']}/")
            get_fic_btn = st.button('Get FanFic!', key=idx)
            if get_fic_btn:
                get_content(row['ID'])


if status == '按标题关键词':
    item = st.text_input('输入一个关键词')
    entered_items = st.empty()

    search_btn = st.button('Search!')

    if st.session_state.get('button') != True:
        st.session_state['button'] = search_btn
    if st.session_state['button'] == True:
        entered_items.markdown("Search fanfics containing " + item + " in their titles")
        with st.spinner("Finding fics..."):

            if not isinstance(item, str) or not len(item) > 0:
                entered_items.markdown(
                    "(请输入至少一个关键字)"
                )
            else:
                for idx, row in full_df.iterrows():
                    if item.lower() in row['Title'].lower():
                        with st.expander(row['Title']):
                            st.markdown(row['Summary'])
                            st.write(f"https://archiveofourown.org/works/{row['ID']}/")
                            get_fic_btn = st.button('Get FanFic!', key=idx)
                            if get_fic_btn:
                                get_content(row['ID'])
                                st.session_state['button'] = False

if status == '搜索全文':
    items = st.text_area(
            '输入关键词(多词组请用英文字符的逗号区分“,”)',
            pure_comma_separation("", return_list=False),
        )
    search_status = st.radio("逻辑关系",['AND','OR'])
    if search_status == 'OR':
        items = pure_comma_separation(items, return_list=False)
    if search_status == 'AND':
        items = pure_comma_separation2(items, return_list=False)
    entered_items = st.empty()

    search_btn = st.button('Search!')

    if st.session_state.get('button') != True:
        st.session_state['button'] = search_btn
    if st.session_state['button'] == True:
        if search_status == 'OR':
            stat = 'any'
        if search_status == 'AND':
            stat = 'all'
        entered_items.markdown(f"Search fanfics mentioning {stat} of the entered keywords in full text")
        with st.spinner("Finding fics..."):

            if not isinstance(items, str) or not len(items) > 0:
                entered_items.markdown(
                    "(请输入至少一个关键字)"
                )
            else:
                st.markdown('以关键词出现频率排序：')
                display_list = []
                for idx, row in full_df.iterrows():
                    if search_status == 'OR':
                        result = search_content(items, row['Content'])
                    if search_status == 'AND':
                        result = search_content2(items, row['Content'])
                    if result>0:
                        display_list.append((idx, result))

                sorted_display_list = sorted(display_list, key=lambda tup: tup[1])[::-1]
                for i, r in sorted_display_list:
                    with st.expander(full_df.loc[i,'Title']):
                        st.markdown('关键词共计出现**'+str(r)+'**次')
                        st.markdown(full_df.loc[i,'Summary'])
                        st.write(f"https://archiveofourown.org/works/{full_df.loc[i,'ID']}/")
                        get_fic_btn = st.button('Get FanFic!', key=i)
                        if get_fic_btn:
                            get_content(full_df.loc[i,'ID'])
                            st.session_state['button'] = False
