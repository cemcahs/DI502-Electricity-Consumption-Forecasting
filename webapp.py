import dash
from dash import Dash, html, dcc, dash_table
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from dash import no_update  # Corrected import for no_update
import pandas as pd
from pandas import date_range
import plotly.graph_objs as go
import io
import xlsxwriter
from lightgbm import LGBMRegressor
import numpy as np
import matplotlib.pyplot as plt
import datetime
import os
from google.cloud import storage
import openpyxl
import shap
import plotly.tools as tls

def read_excel_blob(bucket_name, blob_name):

    """Reads an Excel blob directly into a pandas DataFrame."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    data = blob.download_as_bytes()

    return pd.read_excel(io.BytesIO(data))




def write_dataframe_to_blob(bucket_name, blob_name, dataframe):

    """Writes a DataFrame to an Excel blob in GCS."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Convert DataFrame to BytesIO object
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        dataframe.to_excel(writer)
    output.seek(0)

    # Upload the BytesIO object to GCS
    blob.upload_from_file(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')



# Initialize the Dash app
app = Dash(__name__)

server = app.server

welcome_layout = html.Div([
    html.H1("Welcome to the Electricity Consumption Forecasting Dashboard"),
    html.Br(),
    html.P("With the help of this dash, you will be able to access the machine learning model developed with EPIAS data for Turkey to forecast electricity consumption for desired date range.",style={"font-size": 21}),
    html.Br(),
    html.Br(),
    html.Img(src='https://media.giphy.com/media/lM86pZcDxfx5e/giphy.gif',style={'height': 'auto', 'width': '100vh'})
    # Include any other elements you want on the Welcome page
], style={'margin-top': '50px',"justify-content": "center", "text-align": "center"})

dashboard_layout = html.Div([
    
    html.Img(src="https://mb.cision.com/Public/MigratedWpy/97284/9176690/96d47ec275a08bc0_800x800ar.jpg"),
    
    html.Br(style={"line-height": "2"}),


    # Dropdown or input for forecasting periods
    html.Div([
        html.Label('Choose an end date for prediction:', style={'font-weight': 'bold',"font-size": 21})
    ]),

    html.Br(),
    
    html.Div([
        dcc.DatePickerSingle(
            id='date-picker-single',
            date="2023-12-31",  # Ön tanımlı tarih olarak bugünü kullanabilirsiniz
            display_format='YYYY-MM-DD'
        )]),

    html.Br(style={"line-height": "3"}),

    # Button to trigger forecasting
    html.Button('Forecast', id='forecast-button',style={'width': '10%'}),
    
    html.Br(),
    html.Br(),
    html.Br(),
    
    # Graph to display the forecast
    dcc.Graph(id='forecast-graph',style={'width': '60%'}),
    html.Br(),
    dcc.Graph(id='shap-graph',style={'width': '40%'}),
    
    # Button to download data
    html.Button("Download Forecasts", id="btn_xlsx"),
    dcc.Download(id="download-dataframe-xlsx"),
],

    style={
        'display': 'flex',
        'flex-direction': 'column',  # Stack children vertically
        'justify-content': 'space-around',  # Distribute space around items
        'align-items': 'center',  # Centers items horizontally
        'height': '100vh',  # Use full height of the view port
        'width': '80%',  # Use 80% of the width, you can adjust as needed
        'margin': '0 auto',  # Center the div on the page
        'margin-top': '50px', 
        'margin-bottom': '50px'
    }

)

# Layout for the FAQ page
faq_layout = html.Div([
    html.H1("Frequently Asked Questions"),
    html.P("Here you can find answers to common questions about electricity consumption:",style={"font-size": 21}),

    html.Br(),
    html.P("How was the model for electricity consumption trained? ",style={'font-weight': 'bold',"font-size": 18}),
    html.P("The training, testing and evaluation data has been retrieved to our servers from EPIAS open source platform.",style={"font-size": 18}),

    html.P("Is it possible for the model to overfit or underfit for the consumption data of Turkey?",style={'font-weight': 'bold',"font-size": 18}),
    html.P("The model used more than 2 years of data JUST FOR TRAINING! Thus it is very unlikely to see an overfitting behaviour as the model seen a lot of various trends during the 2 years of data. Also, learning curve of the model is checked.",style={"font-size": 18}),

    html.P("Will the data also be available in the future for providing the most recent forecasts?",style={'font-weight': 'bold',"font-size": 18}),
    html.P("The EPIAS platform is providing the consumption and generation data for various energy sources as a mandatory service due to Turkish legislation. Thus even if this task will be taken away from EPIAS also by Turkish officials, another data sharing platform has to be provided according to aforementioned legislation. Our product is designed to be adapted to a potential new dataset in a few hours thus The Bias Busters are going to keep providing consumption forecasts!",style={"font-size": 18}),
    
    html.P("How reliable are the forecasts?",style={'font-weight': 'bold',"font-size": 18}),
    html.P("Model performance is so high with 0.96 R2 so forecast will be reliable if there is no significant pattern change causing from external factors like new tech or economic crisis.",style={"font-size": 18})
    # Include your FAQ content here
],style={'margin-top': '50px'})

# Layout for the Contact page
contact_layout = html.Div([
    html.H1("Contact Us"),
    html.P("For any question or further inquiries, please contact:",style={"font-size": 18}),
    html.P("cemalicoskunirmak@gmail.com",style={"font-size": 18,'font-weight': 'bold'})],style={'margin-top': '50px'}),



app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div([
        dcc.Link('Welcome || ', href='/',style={'font-family': 'Times New Roman, Times, serif', 'font-weight': 'bold',"font-size": 21}),
        dcc.Link('Forecasting Dash || ', href='/dashboard',style={'font-family': 'Times New Roman, Times, serif', 'font-weight': 'bold',"font-size": 21}),
        dcc.Link('FAQ || ', href='/faq',style={'font-family': 'Times New Roman, Times, serif', 'font-weight': 'bold',"font-size": 21}),
        dcc.Link('Contact', href='/contact',style={'font-family': 'Times New Roman, Times, serif', 'font-weight': 'bold',"font-size": 21}),
    ], className="row"),
    html.Div(id='page-content')
])

@app.callback(Output('page-content', 'children'),
              [Input('url', 'pathname')])

def display_page(pathname):
    if pathname == '/faq':
        return faq_layout
    elif pathname == '/contact':
        return contact_layout
    elif pathname == '/dashboard':
        return dashboard_layout  # Use your existing dashboard layout here
    return welcome_layout  # Default to the Welcome page

@app.callback(
    [Output('forecast-graph', 'figure'),
     Output('shap-graph', 'figure'),
     Output("download-dataframe-xlsx", "data")],
    [Input('forecast-button', 'n_clicks'),
     Input("btn_xlsx", "n_clicks")],
    [State('date-picker-single', 'date')],
    prevent_initial_call=True)

def update_and_download(n_clicks_forecast, n_clicks_download, end_date):
    
    ctx = dash.callback_context

    if not ctx.triggered:
        raise PreventUpdate

    # data_file_path = os.getenv('DATA_FILE_PATH', 'Electricity_Consmption_EPIAS_data.xlsx')
    # prediction_file_path = os.getenv('PREDICTION_FILE_PATH', 'prediction.xlsx')

    start_date=datetime.date(2023, 10, 1)

    bucket_name = 'electricity_consump'
    data_blob_name = 'Electricity_Consmption_EPIAS_data.xlsx'  # The name of the blob in the bucket
    prediction_blob_name = 'prediction.xlsx'

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    best_params = {"learning_rate": 0.11867001834319307,
        "max_depth" : 6, 
        "n_estimators": 474,
        "num_leaves": 29,
        "reg_alpha": 50,
        "reg_lambda": 97,
        "subsample": 0.8}

    if button_id == 'forecast-button':
            
        df = read_excel_blob(bucket_name, data_blob_name)

        dates_dt = pd.to_datetime(df.Tarih, format='%d.%m.%Y')

        df.Tarih = dates_dt.copy()
        df = df.sort_values("Tarih")
    
        df['year']=df['Tarih'].dt.year 
        df['month']=df['Tarih'].dt.month
        df['day']=df['Tarih'].dt.day
        df['season']=df['Tarih'].dt.quarter
        df['week']=df['Tarih'].dt.isocalendar().week
        df['dayofweek']=df['Tarih'].dt.dayofweek
        df['hour']= df.Saat.astype("str").apply(lambda x: x[:2]).astype("int")

        df = df.sort_values(["year","month","day","hour"])

        target = "Tüketim Miktarı (MWh)"

        df[target] =  pd.Series([item.replace(".", "").replace(",",".") for item in df.loc[:,target]]).astype("float")
        
        train = df[df.Tarih <= "2023-09-30"].reset_index(drop=True).copy()

        test_period = date_range(start= start_date, periods=(pd.to_datetime(end_date) - pd.to_datetime(start_date)).days * 24, freq='H')

        x_test = pd.DataFrame(
            {
                "year" : test_period.year,
                "month": test_period.month,
                "day":test_period.day,
                "season":test_period.quarter,
                "week":test_period.isocalendar().week,
                "dayofweek":test_period.dayofweek,
                "hour":test_period.hour
            }
        )

        x_train = train.iloc[:,-7:]
        y_train = train.loc[:,target]

        model = LGBMRegressor(random_state=42,verbose=1,**best_params)
        model.fit(x_train, y_train)

        y_predicted = pd.Series(model.predict(x_test))
        y_predicted.index = test_period
        
        write_dataframe_to_blob(bucket_name, 'prediction.xlsx', pd.DataFrame(y_predicted))
        
        train_index_label = (train.Tarih.astype("str") + " " +   train.Saat.astype("str")).astype("datetime64[ns]")
        
        # Create traces
        trace1 = go.Scatter(
            x = train_index_label[17000:],
            y = train["Tüketim Miktarı (MWh)"].iloc[17000:],
            mode = 'lines',
            name = 'Actual',
            line = dict(color='blue')
        )
        
        trace2 = go.Scatter(
            x = y_predicted.index,  # Assuming predictions align with the actual index
            y = y_predicted,
            mode = 'lines',
            name = 'Prediction',
            line = dict(color='red')
        )

        # Layout
        layout = go.Layout(
            title = 'LightGBM_Tuned_Model',
            xaxis = dict(title='Time'),
            yaxis = dict(title='Kwh'),
            legend = dict(x=0, y=1)
        )

        # Figure
        fig = go.Figure(data=[trace1, trace2], layout=layout)

        shap_values = shap.TreeExplainer(model).shap_values(x_test)
        feature_names = x_test.columns

        mean_abs_shap_values = np.abs(shap_values).mean(axis=0)
        feature_importance = dict(zip(feature_names, mean_abs_shap_values))

        sorted_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=False)

        data = []
        for feature_name, _ in sorted_features:
            feature_index = feature_names.get_loc(feature_name)
            shap_values_feature = shap_values[:, feature_index]
            data.append(go.Scatter(
                y=[feature_name] * len(shap_values_feature),
                x=shap_values_feature,
                mode='markers',
                name=feature_name
            ))


        # Plotly figürünü oluşturun
        fig2 = go.Figure(data=data)

        fig2.update_layout(title_text= "Feature Importance by SHAP Values", title_x=0.5, title_y=0.95,title={"font" : {'family': "Arial Black, sans-serif"}}, xaxis = dict(title='Shap Value (impact on model output)'))

        return fig, fig2, no_update
    
    elif button_id == "btn_xlsx":
        # Assuming the figure data is stored and accessible here
        # You need to ensure that the forecast data is available to be downloaded
        df = read_excel_blob(bucket_name, prediction_blob_name)  # Replace with actual forecast data
        df.columns = ["Date","Tüketim Miktarı (MWh)"]
        return no_update,no_update, dcc.send_data_frame(df.to_excel, "forecast_data.xlsx", sheet_name='Forecast Data')
    else:
        raise PreventUpdate

if __name__ == '__main__':
    app.run_server(debug=True)