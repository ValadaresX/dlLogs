import json

import requests
from bs4 import BeautifulSoup


def coletar_dados(identifier_id):
    url = f"https://www.wowdb.com/spells/{identifier_id}"
    response = requests.get(url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")

        dados_talento = {}

        # Exemplo de extração de dados dinâmicos
        dados_talento["identifier_id"] = identifier_id
        dados_talento["nome"] = soup.find("h1").text
        dados_talento["strength"] = float(soup.find("span", {"class": "strength"}).text)
        dados_talento["agility"] = float(soup.find("span", {"class": "agility"}).text)
        dados_talento["stamina"] = float(soup.find("span", {"class": "stamina"}).text)
        # Adicione outros campos de dados dinâmicos que você deseja coletar

        with open("dados_talentos.json", "a") as file:
            json.dump(dados_talento, file)
            file.write("\n")
    else:
        print(f"Erro ao acessar a página do talento {identifier_id}")


identifier_id = "91008"
coletar_dados(identifier_id)
