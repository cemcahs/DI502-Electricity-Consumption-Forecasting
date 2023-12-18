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

app.layout = html.Div([

    html.Img(src="https://mb.cision.com/Public/MigratedWpy/97284/9176690/96d47ec275a08bc0_800x800ar.jpg"),
    
    # Dropdown or input for forecasting periods
    html.Div([
        dcc.Slider(
            id='forecast-periods',
            min=1,
            max=30,
            step=1,
            value=14,
            marks={i: str(i) for i in range(1, 31)}
        )
    ], style={'width': '80%', 'padding': '20px'}),

    # Button to trigger forecasting
    html.Button('Forecast', id='forecast-button',style={'width': '10%'}),

    # Graph to display the forecast
    dcc.Graph(id='forecast-graph',style={'width': '60%', 'display': 'inline-block'}),

    # Button to download data
    html.Button("Download Excel", id="btn_xlsx"),
    dcc.Download(id="download-dataframe-xlsx")
],

    style={
        'display': 'flex',
        'flex-direction': 'column',  # Stack children vertically
        'justify-content': 'space-around',  # Distribute space around items
        'align-items': 'center',  # Centers items horizontally
        'height': '100vh',  # Use full height of the view port
        'width': '80%',  # Use 80% of the width, you can adjust as needed
        'margin': '0 auto'  # Center the div on the page
    }

)

@app.callback(
    [Output('forecast-graph', 'figure'),
     Output("download-dataframe-xlsx", "data")],
    [Input('forecast-button', 'n_clicks'),
     Input("btn_xlsx", "n_clicks")],
    [State('forecast-periods', 'value')],
    prevent_initial_call=True)

def update_and_download(n_clicks_forecast, n_clicks_download, forecast_periods):
    
    ctx = dash.callback_context

    if not ctx.triggered:
        raise PreventUpdate

    # data_file_path = os.getenv('DATA_FILE_PATH', 'Electricity_Consmption_EPIAS_data.xlsx')
    # prediction_file_path = os.getenv('PREDICTION_FILE_PATH', 'prediction.xlsx')

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

        test_period = date_range(start='2023-10-01 00:00:00', periods=forecast_periods*24, freq='H')

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

        basic_model = LGBMRegressor(random_state=42,verbose=1,**best_params)
        basic_model.fit(x_train, y_train)

        y_predicted = pd.Series(basic_model.predict(x_test))
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
            yaxis = dict(title='Value'),
            legend = dict(x=0, y=1)
        )

        # Figure
        fig = go.Figure(data=[trace1, trace2], layout=layout)

        return fig, no_update
    
    elif button_id == "btn_xlsx":
        # Assuming the figure data is stored and accessible here
        # You need to ensure that the forecast data is available to be downloaded
        df = read_excel_blob(bucket_name, prediction_blob_name)  # Replace with actual forecast data
        df.columns = ["Date","Tüketim Miktarı (MWh)"]
        return no_update, dcc.send_data_frame(df.to_excel, "forecast_data.xlsx", sheet_name='Forecast Data')
    else:
        raise PreventUpdate

if __name__ == '__main__':
    app.run_server(debug=True)