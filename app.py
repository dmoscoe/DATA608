# -*- coding: utf-8 -*-
"""
Created on Sun Nov 21 12:08:23 2021

@author: dmosc
"""

import pandas as pd
import json
import urllib.request
from functools import reduce
import plotly.graph_objects as go
import dash
import dash_html_components as html
import dash_core_components as dcc
import dash_bootstrap_components as dbc
from dash.dependencies import Output, Input

app = dash.Dash(__name__, external_stylesheets = [dbc.themes.BOOTSTRAP])

server = app.server

colors = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52']

states = ["AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"]

fuel_types = {"COW": "Coal",
"PEL": "Petroleum liquids",
"PC": "Petroleum coke",
"NG": "Natural gas",
"OOG": "Other gases",
"NUC": "Nuclear",
"HYC": "Conventional hydroelectric",
"AOR": "Other renewables",
"WND": "Wind",
"SUN": "All utility-scale solar",
"SPV": "Utility-scale photovoltaic",
"STH": "Utility-scale thermal",
"GEO": "Geothermal",
"WWW": "Wood and wood-derived fuels",
"WAS": "Other biomass",
"HPS": "Hydro-electric pumped storage",
"OTH": "Other",
"TSN": "All solar",
"DPV": "Small-scale solar photovoltaic",
"Other": "Other"}

years = list(range(2001, 2022))

#Store data rec'd from API in pulled_data for future use
pulled_data = {}
for state in states:
    pulled_data[state] = {}

def get_retail_sales(state):

    if "retail_sales" in pulled_data[state].keys():
        return pulled_data[state]["retail_sales"]
    else:            
        api_call = "http://api.eia.gov/series/?api_key=c0b197bcf4610007c7e977fccc486830&series_id=ELEC.SALES." + state + "-ALL.M"
        with urllib.request.urlopen(api_call) as url:
            data = json.loads(url.read().decode())
        
        df = pd.DataFrame(
            data['series'][0]['data'],
            columns = ['Date', "energy"])
        
        df['Year'] = df.Date.str.slice(0,4).astype(int)
        df['Month'] = df.Date.str.slice(4,6).astype(int)
        df['TWh'] = df.energy / 1000
        df['xaxis_labels'] = df.Date.str.slice(4,6) + "/" + df.Date.str.slice(0,4)
        df = df.loc[:, ['Year', 'Month', 'TWh', 'xaxis_labels']]
    
        df_Min = pd.DataFrame(df.groupby(['Month'])['TWh'].min()).rename(columns = {'TWh':'Min'})
        df_Q1 = pd.DataFrame(df.groupby(['Month'])['TWh'].quantile([0.25])).rename(columns = {'TWh':'Q1'})
        df_Q3 = pd.DataFrame(df.groupby(['Month'])['TWh'].quantile([0.75])).rename(columns = {'TWh':'Q3'})
        df_Max = pd.DataFrame(df.groupby(['Month'])['TWh'].max()).rename(columns = {'TWh':'Max'})
    
        df_list = [df, df_Min, df_Q1, df_Q3, df_Max]
    
        res = reduce(lambda left, right: pd.merge(left, right, on = ['Month'], how = 'outer'), df_list)
        
        pulled_data[state]["retail_sales"] = res
        return res

def get_net_gen(state, fuel):
    if fuel in pulled_data[state].keys():
        return pulled_data[state][fuel]
    else:
        try:
            api_call = "http://api.eia.gov/series/?api_key=c0b197bcf4610007c7e977fccc486830&series_id=ELEC.GEN." + fuel + "-" + state + "-99.M"
            with urllib.request.urlopen(api_call) as url:
                data = json.loads(url.read().decode())
            df = pd.DataFrame(
                data['series'][0]['data'],
                columns = ['Date', fuel])
        
        except KeyError:
            api_call = "http://api.eia.gov/series/?api_key=c0b197bcf4610007c7e977fccc486830&series_id=ELEC.GEN.ALL-" + state + "-99.M"
            with urllib.request.urlopen(api_call) as url:
                data = json.loads(url.read().decode())
            df = pd.DataFrame(
                data['series'][0]['data'],
                columns = ['Date', fuel])
            df[fuel] = 0
    
        df['Year'] = df.Date.str.slice(0,4).astype(int)
        df['Month'] = df.Date.str.slice(4,6).astype(int)
        df = df.loc[:, ['Year', 'Month', fuel]]
        pulled_data[state][fuel] = df
        return df

def get_net_gens(state, fuels, start, end):
    df_list = []
    fuels.append("ALL")
    
    for fuel in fuels:
        tmp = get_net_gen(state, fuel)
        tmp = tmp[(tmp.Year >= start) & (tmp.Year <= end)]
        df_list.append(tmp)
    
    merged_df = reduce(lambda left, right: pd.merge(left, right, on = ['Year', 'Month'], how = 'outer'), df_list)
    fuels_by_variance = list(merged_df.iloc[:, 2:].var().sort_values().index)
    sorted_df = merged_df[fuels_by_variance]

    sorted_asfractions_df = sorted_df.drop(columns = "ALL").div(sorted_df.ALL, axis = 0)
    cumulative_df = pd.DataFrame({
        'Year': merged_df.Year,
        'Month': merged_df.Month})
    for col in sorted_asfractions_df.columns:
        cumulative_df[col] = sorted_asfractions_df.loc[:, :col].sum(axis = 1)
    
    cumulative_df['xaxis_labels'] = cumulative_df.Month.astype(str) + "/" + cumulative_df.Year.astype(str)
    res = cumulative_df.sort_values(['Year', 'Month']).reset_index(drop = True)
        
    return res

def get_intensity(state):
    if 'intensity' in pulled_data[state].keys():
        return pulled_data[state]['intensity']
    else:
        api_call_population = "http://api.eia.gov/series/?api_key=c0b197bcf4610007c7e977fccc486830&series_id=SEDS.TPOPP." + state + ".A"
        api_call_real_gdp = "http://api.eia.gov/series/?api_key=c0b197bcf4610007c7e977fccc486830&series_id=SEDS.GDPRX." + state + ".A"
        api_call_total_consumption = "http://api.eia.gov/series/?api_key=c0b197bcf4610007c7e977fccc486830&series_id=SEDS.TETCB." + state + ".A"
    
        with urllib.request.urlopen(api_call_population) as url:
            data = json.loads(url.read().decode())
        units = data['series'][0]['units']

        df_pop = pd.DataFrame(
            data['series'][0]['data'],
            columns = ['Year', units])
            
        with urllib.request.urlopen(api_call_real_gdp) as url:
            data = json.loads(url.read().decode())
        units = data['series'][0]['units']
        
        df_real_gdp = pd.DataFrame(
            data['series'][0]['data'],
            columns = ['Year', units])
        
        with urllib.request.urlopen(api_call_total_consumption) as url:
            data = json.loads(url.read().decode())
        units = data['series'][0]['units']
        
        df_total_consumption = pd.DataFrame(
            data['series'][0]['data'],
            columns = ['Year', units])
    
        df_list = [df_pop, df_real_gdp, df_total_consumption]
    
        df_merged = reduce(lambda left,right: pd.merge(left, right, on = ['Year'], how = 'outer'), df_list)
        
        df_merged['perCap'] = df_merged.iloc[:,3] / df_merged.iloc[:,1]
        df_merged['perUSD'] = df_merged.iloc[:,3] / df_merged.iloc[:,2]
        
        df_merged['Year'] = df_merged['Year'].astype(int)
        df_merged = df_merged.sort_values(by = 'Year')
        pulled_data[state]['intensity'] = df_merged
        return df_merged

app.layout = dbc.Tabs([
    dbc.Tab([
        html.Div([
            html.H1('Electricity Consumption and Production'),
            html.B(html.I('States vary in their seasonal patterns of electricity consumption. They also vary in the portfolio of fuels they use to generate electricity. The plots below compare a state\'s electricity consumption to its fuel mix over time.')),
            html.P(),
            ('In the top plot, the red line shows actual retail sales of electricity (a measure of consumption) for a state in a given month. The dark gray region shows where retail sales typically lie for that month based on historical data to 2001. The light gray region extends to the maximum and minimum retail sales for that month since 2001.'),
            html.P(),
            ('The bottom plot shows how different fuel types contribute to a state\'s overall electricity production. Fuel types are stacked according to variance. Fuels with the least variability in production form the base of the graphic, as well as the base of a state\'s electricity generation system.'),
            html.P(),
        ]),
        html.Div([
            dbc.Row([
                dbc.Col(html.Div([
                    html.B('Select a state from the dropdown menu below.'),
                    dcc.Dropdown(id = 'state_dropdown_1',
                        options = [{'label': state, 'value': state}
                            for state in states],
                    value = 'NY',),
                ])),
                dbc.Col(html.Div([
                    html.B('Select fuels.'),
                    dcc.Dropdown(id = 'fuels',
                        options = [{'label':"Coal", 'value':"COW"},
                            {'label':"Petroleum liquids",'value':"PEL"},
                            {'label':"Petroleum coke",'value':"PC"},
                            {'label':"Natural gas",'value':"NG"},
                            {'label':"Other gases",'value':"OOG"},
                            {'label':"Nuclear",'value':"NUC"},
                            {'label':"Conventional hydroelectric",'value':"HYC"},
                            {'label':"Other renewables",'value':"AOR"},
                            {'label':"Wind",'value':"WND"},
                            {'label':"All utility-scale solar",'value':"SUN"},
                            {'label':"Utility-scale photovoltaic",'value':"SPV"},
                            {'label':"Utility-scale thermal",'value':"STH"},
                            {'label':"Geothermal",'value':"GEO"},
                            {'label':"Other biomass",'value':"WAS"},
                            {'label':"Hydro-electric pumped storage",'value':"HPS"},
                            {'label':"All solar",'value':"TSN"},
                            {'label':"Small-scale solar photovoltaic",'value':"DPV"}],
                        value = ['NG', 'NUC'], 
                        multi = True),
                    html.P(),
                ])),
             ]),
            dbc.Row([
                dbc.Col(html.Div([
                     html.B('Select a starting year.'),
                     dcc.Dropdown(id = 'start_1',
                        options = [{'label': year, 'value': year}
                            for year in years],
                    value = 2019,),
                ])),
                 dbc.Col(html.Div([
                     html.B('Select an ending year.'),
                     dcc.Dropdown(id = 'end_1',
                        options = [{'label': year, 'value': year}
                            for year in years],
                    value = 2021,),
                ])),
            ]),
        html.P(),
        ]),
        html.Div([
            dcc.Graph(id = 'consumption',),
            dcc.Graph(id = 'generation',),

            html.P(),
            ('Some questions that could be answered with these plots include:'),
            html.P(),
            html.I('How does a state\'s electricity consumption vary seasonally?'),
            html.Ul('Select Missouri (MO) for the period 2019-2021. Consumption peaks twice yearly, with a major peak in the summer and a minor peak in January.'),
            html.I('About how much electricity does a state typically consume during January?'),
            html.Ul('Select Washington (WA) for the period 2015-2018. Typical January consumption is between 8.5 and 9 TWh. However, January 2017 showed greater than usual consumption of about 9.5 TWh.'),
            html.I('How has a state\'s electricity generation portfolio changed over time?'),
            html.Ul('Select Iowa (IA) for the period 2015-2021, and select Coal, Natural Gas, Wind, and Nuclear from the fuels checklist. Notice that Iowa shut down its sole nuclear plant in September 2020. A growing share of electricity generation in Iowa has been due to wind, although when demand is highest during the summer months, some share of production transfers from wind to coal.'),
            html.I('What fuel sources are most sensitive to changes in consumption?'),
            html.Ul('Select New York (NY) for the period 2008-2012, and select Coal, Natural Gas, Nuclear, and Conventional Hydroelectric from the checklist. Notice that during periods of high consumption, natural gas produces a greater share of electricity in New York, and nuclear a smaller share.'),
        ]),
    ], style = {'padding': 50}, label = 'Con/Prod'),
    dbc.Tab([
        html.Div([
        html.H1('Energy intensity'),
        html.B(html.I('States vary in energy intensity, the ratio of energy consumed to total economic output (GDP). The plot below compares a state\'s GDP, energy intensity, and population over time.')),
        html.P(),
        ('In the plot below, each state is represented by a path through the plot area. Starting and ending years are labeled, and intermediate years are represented by points along the path. A single path shows the relationship between a state\'s GDP and energy intensity. Usually increases in GDP are associated with decreases in energy intensity.'),
        html.P(),
        ('GDP and energy intensity are related to population. The bubbles at the endpoints of each path give a rough measure of net population change for a state over the time interval. For all paths the size of the bubble at the beginning of the path is the same, so populations cannot be compared across states.'),
        html.P(),
        ]),
        html.Div([
            dbc.Row([
                dbc.Col(
                    html.Div([
                        html.B('Select states from the dropdown menu below.'),
                        dcc.Dropdown(id = 'state_multidropdown_2',
                            options = [{'label': state, 'value': state}
                                for state in states],
                            value = ['NY'],
                            multi = True),
                    ])
                ),
                dbc.Col(
                    html.Div([
                        html.B('Select a starting year.'),
                        dcc.Dropdown(id = 'start_2',
                            options = [{'label': year, 'value': year}
                                for year in years],
                            value = 2015,),
                    ])
                ),
                dbc.Col(
                    html.Div([
                        html.B('Select an ending year.'),
                        dcc.Dropdown(id = 'end_2',
                            options = [{'label': year, 'value': year}
                                for year in years],
                            value = 2019,),
                    ])
                ),
            ]),
        ]),
        dcc.Graph(id = 'intensities', style = {'width': '90vh'}),
        ('Some questions that could be answered with this plot include:'),
        html.P(),
        html.I('How does energy intensity change with a state\'s GDP?'),
        html.Ul('Select New York (NY) for the period 2015-2019. GDP increased steadily, and energy intensity showed an overall downward trend. However, the period 2017-2018 showed a slight increase in energy intensity.'),
        html.I('How does a natural disaster affect the relationship between a state\'s economic output and energy usage?'),
        html.Ul('Select Louisiana (LA) for the period 2003-2010. For the period 2003-2005, GDP increased steadily, and energy intensity decreased. Hurricane Katrina marks a sharp turning point for Louisiana, beginning a period of decline in GDP and increased energy intensity. After 2007, the state returned to a trajectory of progress, with slowly increasing GDP and decreasing energy intensity.'),
        html.I('How do states compare in GDP, energy intensity, and population change?'),
        html.Ul('Select California, Florida, New York, and Texas for the period 2001-2019. These states represent the largest economies in the USA. All four states show steady overall increasing GDP and declining energy intensity. New York alone shows no discernible increase in population over this period. The economy of Texas is much more energy intensive than that of other states with similar GDP. All four states show a temporary reversal of trend around 2008, the time of the financial crisis.'),
        ],
    style = {'padding': 50}, label = "Intensity"),
]) #dbc.Tabs

@app.callback(Output('consumption', 'figure'),
              Input('state_dropdown_1', 'value'),
              Input('start_1', 'value'),
              Input('end_1', 'value'))
def plot_retail_sales(state, start, end):
    df = get_retail_sales(state)
    df = df[(df.Year >= start) & (df.Year <= end)].sort_values(['Year', 'Month']).reset_index(drop = True)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x = df.index,
        y = df.Min,
        line = dict(color = '#c5c6c7'),
        line_shape = 'spline',
        name = "Max, Min"))
    fig.add_trace(go.Scatter(
        x = df.index,
        y = df.Max,
        fill = 'tonexty',
        line = dict(color = '#c5c6c7'),
        line_shape = 'spline',
        showlegend = False))
    fig.add_trace(go.Scatter(
        x = df.index,
        y = df.Q1,
        line = dict(color = '#1f2833'),
        line_shape = 'spline',
        name = "Q1, Q3"))
    fig.add_trace(go.Scatter(
        x = df.index,
        y = df.Q3,
        fill = 'tonexty',
        line = dict(color = '#1f2833'),
        line_shape = 'spline',
        showlegend = False))
    fig.add_trace(go.Scatter(
        x = df.index,
        y = df.iloc[:,2],
        line = dict(color = '#fc4445'),
        line_shape = 'spline',
        name = "Retail Sales"))
    
    fig.update_layout(
        xaxis = dict(
            tickmode = 'array',
            ticktext = df.xaxis_labels[(df.index + 1) % 3 == 0],
            tickvals = df.index[(df.index + 1) % 3 == 0]),
        legend = dict(
            yanchor = "top",
            y = 0.99,
            xanchor = "left",
            x = 0.01),
        title = "Electricity Consumption and Production, " + state + ", " + str(start) + " to " + str(end),
        xaxis_title = "",
        yaxis_title = "Consumption (TWh)",
        showlegend = True)

    return fig

@app.callback(Output('generation', 'figure'),
              Input('state_dropdown_1', 'value'),
              Input('fuels', 'value'),
              Input('start_1', 'value'),
              Input('end_1', 'value'))
def plot_net_gens(state, fuels, start, end):
    df = get_net_gens(state, fuels, start, end)
    fig = go.Figure()
    for c in range(2, len(df.columns) - 1):
        fig.add_trace(go.Scatter(
            x = df.index,
            y = df.iloc[:, c],
            mode = 'lines',
            line_shape = 'spline',
            fill = 'tonexty',
            name = fuel_types[df.columns[c]]))
    fig.update_layout(
        xaxis = dict(
            tickmode = 'array',
            ticktext = df.xaxis_labels[(df.index + 1) % 3 == 0],
            tickvals = df.index[(df.index + 1) % 3 == 0]),
        yaxis = dict(
            type = 'linear',
            range = [0, 1],
            title = "Cumulative fraction of production"),
        legend = dict(
            yanchor = "top",
            y = 0.99,
            xanchor = "left",
            x = 0.01)
    )
    return fig

@app.callback(Output('intensities', 'figure'),
              Input('state_multidropdown_2', 'value'),
              Input('start_2', 'value'),
              Input('end_2', 'value'))
def plot_intensity(states, start, end):
    #Label only the bubbles, and put markers along the lines.
    intensities = []
    for state in states:
        tmp = get_intensity(state)
        tmp = tmp[(tmp.Year >= start) & (tmp.Year <= end)]
        intensities.append(tmp)

    fig = go.Figure()

    for i in range(len(states)):
        
        #Bubbles. All first bubbles have size 25. All second bubbles have size proportional to first bubble.
        fig.add_trace(go.Scatter(
            x = [intensities[i].iloc[0,2], intensities[i].iloc[-1,2]],
            y = [intensities[i].iloc[0,5], intensities[i].iloc[-1,5]],
            text = intensities[i].iloc[[0,-1], 0],
            mode = 'markers+text',
            showlegend = False,
            marker = dict(
                color = colors[i],
                size = [25, 25 * (intensities[i].iloc[-1,1]/intensities[i].iloc[0,1])]
            )
        ))

        fig.add_trace(go.Scatter(
            x = intensities[i].iloc[:, 2], #GDP
            y = intensities[i].iloc[:, 5], #perUSD
            line_color = colors[i],
            mode = 'lines+markers',
            line_shape = 'spline',
            name = states[i]
        ))

    fig.update_traces(textposition = 'top center')

    fig.update_layout(
        xaxis = dict(
            title = "Real GDP (millions of 2012 dollars)"),
        yaxis = dict(
            title = "Energy Intensity (thousands of BTUs per dollar)"),
        title = "GDP and Energy Intensity, " + str(start) + " to " + str(end))
    
    return fig

if __name__ == '__main__':
    app.run_server(debug = True)