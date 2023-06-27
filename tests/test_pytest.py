from xml.etree import ElementTree as ET

import pytest
from requests import Response

from scripts.copy_logs import (
    filter_key_tag,
    get_new_keys,
    get_remote_xml_data,
    get_status_code,
)


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
    Testa a função 'filter_key_tag' que extrai as chaves do XML de dados
    fornecido e as retorna como um conjunto.O teste compara o resultado
    da função com um conjunto esperado de chaves extraídas do XML fornecido.

    Args:
        None

    Returns:
        None

    Raises:
        AssertionError: se a validação falhar.
    """

    keys_xml = {
        "0000032d4670450f735dbde7d1fd0c3b",
        "00000948a8751f20ef7405c3b3bec537",
    }
    url_base = "https://storage.googleapis.com/wowarenalogs-log-files-prod/"
    expected_result = {
        "https://storage.googleapis.com/wowarenalogs-log-files-prod/0000032d4670450f735dbde7d1fd0c3b",
        "https://storage.googleapis.com/wowarenalogs-log-files-prod/00000948a8751f20ef7405c3b3bec537",
    }
    result = get_new_keys(keys_xml, url_base)
    assert result == expected_result
