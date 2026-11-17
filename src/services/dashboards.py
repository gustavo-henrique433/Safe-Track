import dash
from dash import html, dcc
import plotly.express as px
import pandas as pd
from sqlalchemy import create_engine

app = dash.Dash(__name__) ##Inicio o servidor do Dash

engine = create_engine('sqlite:///src/database/hermes.db')

query = """ 


"""



df = pd.read_sql(query, engine) ##Executa a query e guarda os dados na variavel df

# O Plotly le a tabela df e cria a variavel 'figura' que contem o grafico pronto
figura = px.bar(df, x='nome', y='acessos', title='Top 5 - Patrimonios Mais Buscados')

# Tudo que for aparecer na tela deve estar dentro da lista 'children'
app.layout = html.Div(children=[
    # Cabecalho
    html.H1("Safe-Track Analytics"),
    html.P("Monitoramento de movimentacao via RFID."),
    
    # O componente que exibe graficos recebe a 'figura' que geramos no Passo 3
    dcc.Graph(
        id='grafico-barras-acesso',
        figure=figura
    )
])


#Rodo o servidor
if __name__ == '__main__':
    app.run_server(debug=True, port=8050)
