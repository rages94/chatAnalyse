# -*- coding: utf-8 -*-
import datetime as dt
import re
import dash
from dash.dependencies import Input, Output, State, Event
import dash_core_components as dcc
import dash_html_components as html
import dash_table_experiments as dte
import pandas as pd
import plotly
import plotly.plotly as py
from plotly.offline import iplot, init_notebook_mode
import plotly.graph_objs as go
import cufflinks as cf
import seaborn as sns

import numpy as np
import json
import base64
import io
import sys

cf.go_offline()


# plotly.tools.set_credentials_file(username='RAgE_S', api_key='olc6rqZajRKOuNvXSuc8')

def load_file(file):
    f = open(file, mode='rt', encoding='utf-8')
    lines = [line.split() for line in f]
    f.close()
    return lines


def sortByDate(data):
    return data[0]


def preparation(lines):
    data = []

    for line in lines:
        line = line.split()
        if not line:
            # exclude empty lines
            continue
        else:
            find_date = re.findall(r'\d{2}\.\d{2}\.\d{4}', line[0])

            if find_date and (line[0][0] == "[" or line[0][1] == "["):

                personX = line[2]
                person_X = line[3]

                # new message
                if personX[-1] == ":" or person_X[-1] == ":":
                    # date, time, Nickname, text
                    date = find_date[0]  # date
                    time = line[1][0:-1]  # time

                    if personX[-1] == ":":
                        if personX[0] == "\u202a":  # personX[0] != "P":
                            Nickname = personX[1:-2]
                            text = " ".join(line[3:])
                        else:
                            Nickname = personX[:-1]
                            text = " ".join(line[3:])
                    else:
                        if line[2][0] == "\u202a":
                            Nickname = line[2][1:] + " " + line[3][:-2]
                            text = " ".join(line[4:])
                        else:
                            Nickname = line[2] + " " + line[3][:-1]
                            text = " ".join(line[4:])

                    # separation on the session
                    day, month, year = date.split('.')
                    hour, minute, sec = time.split(':')
                    date = dt.datetime(int(year), int(month), int(day),
                                       int(hour), int(minute), int(sec))

                else:
                    # exclude the technical replicas
                    continue

                data.append([date, Nickname, text])

            else:
                # add the text in previous data
                data[-1][2] = data[-1][2] + "\n" + " ".join(line[:])
                continue

    for msg in data:
        msg[2] = msg[2].replace("\u200e", "")
        msg[2] = re.sub('[^\d\sA-Za-zА-Яа-яё.,!?%/]{2,}', "<smile>", msg[2])
        msg[2] = re.sub('[^\d\sA-Za-zА-Яа-яё.,!?/\'\"\\:;<>@#№$%\^&*-_+=–—]', "<smile>", msg[2])

    return data


def update_sessions(data, interval=180):
    # interval in minutes
    sessions = []
    sess = []
    column = []
    msg1 = ""
    for line in data:
        date = line[0]
        Nickname = line[1]
        if msg1:
            delta_time = date - msg1
            if delta_time.seconds > interval * 60 or delta_time.days != 0:
                sessions.append(sess)
                column.append(len(sessions) + 1)
                sess = [[date, Nickname]]
            else:
                sess.append([date, Nickname])
                column.append(len(sessions) + 1)
        else:
            sess.append([date, Nickname])
            column.append(len(sessions) + 1)

        msg1 = date
    sessions.append(sess)
    return column, sessions


def prep_sess(sessions):
    ne = []
    for i, session in enumerate(sessions):
        a = round((session[-1][0] - session[0][0]).seconds / 60)
        ne.append([i + 1, len(session), a])
    labels = ['Session', 'Number of messages', 'Duration_min']
    dfne = pd.DataFrame.from_records(ne, columns=labels)
    return dfne


def update_response(sessions):
    ne = []
    n_sess = None
    for i, session in enumerate(sessions):
        for mess in session:
            if n_sess == i:
                if speaker == mess[1]:
                    ne.append(resp)
                else:
                    resp = speaker
                    speaker = mess[1]
                    ne.append(resp)
            else:
                resp = mess[1]
                speaker = mess[1]
                ne.append(resp)
                n_sess = i
    return ne


def def_df(data, map_weekday=False):
    # create dataframe
    labels = ['Date', 'Nickname', 'Message']
    df = pd.DataFrame.from_records(data, columns=labels)
    # create column Day of week
    df.index = df.Date
    #     df.drop("Date", axis=1, inplace=True)
    if map_weekday:
        df["Day of week"] = map_weekday(df)
    else:
        df["Day of week"] = df.index.weekday
    return df


def map_weekday(dataF):
    dayofweek = []
    dict_dow = {0: "Понедельник",
                1: "Вторник",
                2: "Среда",
                3: "Четверг",
                4: "Пятница",
                5: "Суббота",
                6: "Воскресенье"}
    for day in dataF.index.weekday:
        dayofweek.append(dict_dow[day])

    return dayofweek


app = dash.Dash()

app.config.suppress_callback_exceptions = True

app.layout = html.Div([
    dcc.Upload(
        id='upload_data',
        children=html.Div([
            'Drag and Drop or ',
            html.A('Select Files')
        ]),
        style={
            'width': '99%',
            'height': '60px',
            'lineHeight': '60px',
            'borderWidth': '1px',
            'borderStyle': 'dashed',
            'borderRadius': '5px',
            'textAlign': 'center',
            'margin': '10px'
        },
        # Allow multiple files to be uploaded
        multiple=True
    ),

    html.Div(id='df_div', style={'display': 'none'}),
    html.Div(id='interval_div', style={'display': 'none'},
             children=[html.Label('Interval(min): '),
                       dcc.Input(id='interval',
                                 value=180,
                                 type='number',
                                 min=0,
                                 required=True
                                 ),
                       html.Br(),
                       html.Br(),
                       html.Br(),
                       html.Label('Range of messages:'),
                       dcc.RangeSlider(id="sld",
                                       count=1,
                                       min=0,
                                       max=1,
                                       value=[0, 1]
                                       )
                       ]
             ),
    html.Div(id='output_data_upload'),
    html.Div(id='lines_div', style={'display': 'none'}),
    html.Div(id='diagram_div'),
    html.Div(id='test_div', style={'display': 'none'}),
    html.Div(dte.DataTable(rows=[{}]), style={'display': 'none'})
])


@app.callback(Output('lines_div', 'children'),
              [Input('upload_data', 'contents'),
               Input('upload_data', 'filename')])
def create_lines(contents, filenames):
    if contents:
        content_strings = []
        count_txt = 0
        for content in contents:
            content_strings.append(content.split(',')[1])

        content_string = "\n".join(content_strings)

        decoded = base64.b64decode(content_string)

        for name in filenames:
            if 'txt' in name:
                count_txt += 1

        #         try:
        if count_txt == len(filenames):
            lines = decoded.decode('utf-8')
            return lines


#         except Exception as err:
#             print(err)
#             return html.Div([
#                 'There was an error processing this file.'
#             ])


@app.callback(Output('df_div', 'children'),
              [Input('lines_div', 'children'),
               Input('interval', 'value'), ])
def create_df(lines, interval):
    if lines and not isinstance(lines, list):
        data = preparation(lines.splitlines())
        data.sort()
        col, sessions = update_sessions(data, interval)
        df = def_df(data)
        df['Session'] = col
        df["Answer to"] = update_response(sessions)
        return df.to_json(date_format='iso', orient='split')


@app.callback(Output('output_data_upload', 'children'),
              [Input('lines_div', 'children'),
               Input('df_div', 'children'),
               Input('sld', 'value')])
def create_table(lines, df, val):
    if lines and not isinstance(lines, list):

        df = pd.read_json(df, orient='split')
        if not val:
            x = len(df)
            val = [0, x]
        return html.Div([
            # Use the DataTable prototype component:\
            # github.com/plotly/dash-table-experiments
            dte.DataTable(rows=df[val[0]:val[1]].to_dict('records')),
            html.Hr()
        ])


@app.callback(Output('interval_div', 'style'),
              [Input('output_data_upload', 'children')])
def show_input(p):
    if p:
        return {'display': 'inline'}
    return {'display': 'none'}


@app.callback(Output('sld', 'max'),
              [Input('df_div', 'children')])
def slider_max(df):
    if df:
        df = pd.read_json(df, orient='split')
        return len(df)


@app.callback(Output('sld', 'value'),
              [Input('sld', 'max')])
def slider_val(max):
    if max:
        return [0, max]


@app.callback(Output('diagram_div', 'children'),
              [Input('df_div', 'children'),
               Input('sld', 'value')])
def show_diagrams(df, val):
    if df:
        df = pd.read_json(df, orient='split')
        df = df[val[0]:val[1]]

        # other statistics
        cnt_audio = len(df[df['Message'] == '<аудиофайл отсутствует>'])
        cnt_video = len(df[df['Message'] == '<видео отсутствует>'])
        cnt_gif = len(df[df['Message'] == '<GIF отсутствует>'])
        cnt_image = len(df[df['Message'] == '<изображение отсутствует>'])
        y_stat = [cnt_audio, cnt_video, cnt_gif, cnt_image]
        label = ['Audio', 'Video', 'GIF files', 'Images']

        # heatmap number of messages by month
        bymonth = df.pivot_table(index=df.index.month,
                                 columns=df.index.year,
                                 aggfunc='count',
                                 values="Message").fillna(0)
        bymonth = bymonth.iplot(kind='heatmap',
                                colorscale='Reds',
                                asFigure=True,
                                title='Number of message by month',
                                xTitle='Month',
                                gridcolor='Black')

        # heatmap number of messages by hour
        byhour = df.pivot_table(index=df.index.hour,
                                columns=df['Nickname'],
                                aggfunc='count',
                                values="Message").fillna(0)
        byhour = byhour.iplot(kind='heatmap',
                              colorscale='Reds',
                              asFigure=True,
                              title='Number of message by hour',
                              xTitle='Hours')

        bypart = df.groupby('Nickname')['Message'].count()
        label_bypart = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        dof = df.groupby('Day of week')['Message'].count()

        return [dcc.Graph(figure=
        go.Figure(data=[
            go.Bar(x=bypart.index,
                   y=bypart.values,
                   marker=dict(color='rgb(245,80,60)',
                               line=dict(
                                   color='rgb(100,0,0)',
                                   width=1.5)
                               ),
                   )],
            layout=go.Layout(
                title='Number of messages by participants:')
        ),
            id='freq_message'),

            dcc.Graph(figure=
            go.Figure(data=[
                go.Bar(x=label_bypart,
                       y=dof.values,
                       marker=dict(color='rgb(250,100,70)',
                                   line=dict(
                                       color='rgb(100,0,0)',
                                       width=1.5)
                                   )
                       )],
                layout=go.Layout(
                    title='Message statistics by days of week',
                    colorway='Red')
            ),
                id='stat_dof'),

            dcc.Graph(figure=
            go.Figure(data=[
                go.Bar(x=label,
                       y=y_stat,
                       marker=dict(color='rgb(245,80,60)',
                                   line=dict(
                                       color='rgb(100,0,0)',
                                       width=1.5)
                                   ),
                       )],
                layout=go.Layout(
                    title='Other statistics:')
            ),
                id='other_stat'),

            dcc.Graph(figure=bymonth, id='heatmap_month'),
            dcc.Graph(figure=byhour, id='heatmap_hour')
        ]


app.run_server(debug=True)