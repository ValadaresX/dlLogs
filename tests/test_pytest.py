import pytest
from requests import Response

from scripts.copy_logs import get_status_code


@pytest.mark.parametrize("status_code", [200, 400, 404, 500])
def test_status_code(status_code):
    """
    Teste o código de status retornado pelo objeto Response em relação ao
    código de status esperado e à mensagem de erro. Recebe um único parâmetro
    `status_code`, que é o código de status esperado a ser testado.

    :param status_code: Um int que representa o código de status esperado.
    :return: None
    """
    status_errors = {
        200: "Success",
        400: "Bad Request: Invalid input data",
        404: "Not Found: The requested resource was not found",
        500: "Internal Server Error: Something went wrong on the server side",
    }

    response = Response()
    response.status_code = status_code

    assert get_status_code(response) == status_code, (
        f"Erro no status code {status_code}: "
        f"Esperado {status_code} - {status_errors.get(status_code)}, "
        f"obtido {response.status_code} - "
        f"{status_errors.get(response.status_code, 'Unknown')}"
    )
