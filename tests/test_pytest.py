import os
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

import pytest
from requests import Response

from scripts.convert_logs import eventArgLengthDictionary, splitEvent
from scripts.copy_logs import (
    download_text_files,
    filter_key_tag,
    get_new_keys,
    get_remote_xml_data,
    get_status_code,
    url_base,
)

# from requests_mock import Mocker


def test_status_code():
    """
    Testa o código de status retornado pelo objeto Response em relação ao código
    de status esperado e à mensagem de erro. O teste falhará se o código de
    status retornado não for 200. Se o código de status retornado for diferente
    de 200, a função identificará o código de status e fornecerá uma descrição
    do que ele significa.

    Retorno: None"""
    response = Response()
    response.status_code = 200

    status_errors = {
        200: "Success",
        400: "Bad Request: Invalid input data",
        404: "Not Found: The requested resource was not found",
        500: "Internal Server Error: Something went wrong on the server side",
    }

    assert get_status_code(response) == 200, (
        f"Erro no status code {response.status_code}: "
        f"{status_errors.get(response.status_code, 'Unknown')}"
    )


def test_get_remote_xml_data():
    """
    Essa função é um teste de unidade que verifica a exatidão da função
    get_remote_xml_data. Ela recupera uma cadeia de caracteres XML da
    função get_remote_xml_data e valida que a tag raiz é igual a
    "{http://doc.s3.amazonaws.com/2006-03-01}ListBucketResult".
    Essa função não recebe nenhum parâmetro nem retorna
    nada. Ela gera um AssertionError se a validação falhar.
    """
    xml_str = get_remote_xml_data()
    root = ET.fromstring(xml_str)
    assert root.tag == "{http://doc.s3.amazonaws.com/2006-03-01}ListBucketResult"


def test_filter_key_tag():
    """
    Testa a função filter_key_tag para verificar se retorna as chaves
    esperadas do XML fornecido.

    :return: None
    """
    xml_data = (
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<ListBucketResult xmlns='http://doc.s3.amazonaws.com/2006-03-01'>"
        "<Name>wowarenalogs-log-files-prod</Name>"
        "<Prefix/>"
        "<Marker/>"
        "<NextMarker>005c9252e4bce3943bd9acd273d34e3f</NextMarker>"
        "<IsTruncated>true</IsTruncated>"
        "<Contents>"
        "<Key>0000032d4670450f735dbde7d1fd0c3b</Key>"
        "<Generation>1685472079879993</Generation>"
        "<MetaGeneration>1</MetaGeneration>"
        "<LastModified>2023-05-30T18:41:19.956Z</LastModified>"
        '<ETag>"a4bedfc634288a5fb5ba06b8f558fe94"</ETag>'
        "<Size>3408912</Size>"
        "</Contents>"
        "<Contents>"
        "<Key>00000948a8751f20ef7405c3b3bec537</Key>"
        "<Generation>1675307181740248</Generation>"
        "<MetaGeneration>2</MetaGeneration>"
        "<LastModified>2023-02-02T03:06:21.851Z</LastModified>"
        '<ETag>"1474df2e2aefea2d1f497dd3ba73c714"</ETag>'
        "<Size>344519</Size>"
        "</Contents>"
        "</ListBucketResult>"
    )
    expected_keys = {
        "0000032d4670450f735dbde7d1fd0c3b",
        "00000948a8751f20ef7405c3b3bec537",
    }
    assert filter_key_tag(xml_data) == expected_keys


def test_get_new_keys():
    """
    Testa a função 'get_new_keys' que retorna um conjunto
    de chaves ausentes com base nas chaves encontradas,
    diretório de logs fornecido e URL base.
    Args: None

    Returns: None

    Raises:
        AssertionError: Se o resultado retornado pela função
        não for igual ao conjunto esperado de chaves ausentes.
    """
    found_keys = {
        "0000032d467045bde7d1fd0c3b",
        "00000948a8751405c3b3bec537",
    }

    logs_dir = Path("scripts/logs/")

    expected_result = {
        url_base + "0000032d467045bde7d1fd0c3b",
        url_base + "00000948a8751405c3b3bec537",
    }

    assert get_new_keys(found_keys, url_base, logs_dir) == expected_result


def test_download_text_files(mocker):
    # Cria um diretório temporário para o teste
    with TemporaryDirectory() as tmpdir:
        # Define as URLs de teste
        new_keys = {
            "https://example.com/00000U123456789",
            "https://example.com/00000X123456790",
        }

        # Mock da resposta da requisição HTTP
        mock_response = mocker.Mock()
        mock_response.headers.get.return_value = "1024"
        mock_response.iter_content.return_value = (b"Test content" for _ in range(1024))

        # Mock da função 'requests.get'
        mocker.patch("requests.get", return_value=mock_response)

        # Mock da função 'chardet.detect'
        mocker.patch("chardet.detect", return_value={"encoding": "utf-8"})

        # Chama a função com os parâmetros de teste
        download_text_files(new_keys, tmpdir)

        # Verifica se os arquivos foram salvos corretamente
        for url in new_keys:
            filename = os.path.join(tmpdir, urlparse(url).path.split("/")[-1])
            assert os.path.isfile(filename)


# @pytest.mark.convert_logs
def test_eventArgLengthDictionary():
    lines = [
        "11/17 21:13:49.617  ARENA_MATCH_START,572,0,Rated Solo Shuffle,0",
        "11/17 21:13:49.617  COMBATANT_INFO,Player-3684-0DEBA294,0,371,1772,3133,306,0,0,0,533,533,533,0,0,332,332,332,0,523,799,799,799,740,577,[(91008,112928,1),(91018,112939,1),(91030,112953,1),(91007,112927,1),(90914,112823,1),(90925,112834,1),(90932,112842,1),(90941,112852,2),(91028,112951,2),(90940,112851,1),(91015,112936,2),(90933,112844,1),(90922,112831,1),(90936,112847,2),(90921,112830,1),(91026,112949,2),(91003,112923,1),(90993,112911,1),(91027,112950,1),(90992,112909,1),(90938,112849,1),(90915,112824,1),(90935,112846,2),(91002,112921,1),(90927,112837,1),(90926,112836,1),(91000,112918,2),(91004,112924,2),(91006,112926,1),(90924,112833,1),(90934,112845,1),(90939,112850,1),(90948,112861,1),(91019,112940,1),(90920,112829,2),(91014,112935,1),(90916,112825,2),(90917,112826,1),(90918,112827,1),(90919,112828,1),(91013,112934,1),(90942,112853,1)],(0,356510,205604,213480),[4,4,[],[(1122),(1123),(1124),(1126),(1128),(1130),(1135),(1136),(1819),(1821),(1823),(1824)],[(151,226),(130,226),(131,226),(153,226),(200,226),(135,226)]],[(193800,278,(),(9158,6652,7937,1500,4785),()),(199383,252,(),(6652,7578,8936),()),(199361,252,(),(6652,8936),()),(0,0,(),(),()),(172250,262,(),(6893,7881,7960),()),(199362,252,(),(6652,7578,8936),()),(190627,252,(),(7189,8133,8116,6652,1498,6646),()),(192327,281,(),(8302,1576,6646),()),(199363,252,(),(6652,7578,8936),()),(199358,252,(),(6652,8936),()),(192391,265,(),(8290,1543,6616),()),(199381,252,(),(6652,7578,8936),()),(192412,265,(),(8290,1543,6616),()),(188775,262,(),(7534,1521,6646),()),(199384,252,(),(6652,8936),()),(201305,278,(),(6652),()),(199416,252,(),(6652,8936),()),(0,0,(),(),())],[],90,0,863,312",
        '11/17 21:13:49.617  SPELL_AURA_REMOVED,Pet-0-3133-572-18467-1860-0403158EDC,"Grimmon",0x1112,0x0,Pet-0-3133-572-18467-1860-0403158EDC,"Grimmon",0x1112,0x0,32727,"Arena Preparation",0x1,BUFF',
    ]

    expected_result = {
        "Event1": {2, 4},
        "Event2": {3},
    }

    assert eventArgLengthDictionary(lines) == expected_result


@pytest.mark.convert_logs
def test_splitEvent():
    # Arrange
    line = "1/1/2022 12:00:00.000   Event1,Arg1,Arg2"

    # Act
    result = splitEvent(line)

    # Assert
    assert result.group(1) == "1/1/2022"
    assert result.group(2) == "12:00:00.000"
    assert result.group(3) == "Event1"
    assert result.group(4) == "Arg1,Arg2"
