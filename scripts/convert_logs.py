import re
from collections import defaultdict


def getEventType(line) -> str:
    """
    Retorna o tipo de evento a partir da linha fornecida.
    :param line: Uma string contendo o tipo de evento e outras informações.
    :type line: str
    :return: Uma string representando o tipo de evento.
    :rtype: str
    """
    return line.split("  ")[1].split(",")[0]


def getAllUniqueEventTypes(lines) -> set:
    """
    Retorna todos os tipos de eventos únicos a partir de uma lista de linhas de eventos.
    :param lines: Uma lista de linhas de eventos.
    :type lines: list
    :return: Um conjunto contendo os tipos de eventos únicos.
    :rtype: set
    """
    events = set(map(getEventType, lines))
    return events


def getArgs(line) -> list:
    """
    Divide uma string em uma lista de argumentos.

    Args:
        line (str): A cadeia de caracteres de entrada.

    Retorna:
        list: Uma lista de argumentos extraídos da cadeia de caracteres de entrada.
    """
    return line.split("  ")[1].split(",")[1:]


def splitEvent(line) -> re.Match:
    """
    Divide uma linha de evento em seus componentes.

    Args:
        line (str): A linha de evento a ser dividida.

    Retorna:
        re.Match: Um objeto de correspondência que contém os componentes da linha do evento.
    """
    pattern = re.compile(r"(\d\/\d+)\s(\d+\:\d+\:\d+\.\d+)\s\s(\w+),(.+)")
    return pattern.match(line)


def peakLines(lines, numLines=10) -> list:
    """
    Retorna as primeiras `numLines` linhas da lista `lines` fornecida.

    Parâmetros:
        lines (lista): Uma lista de cadeias de caracteres que representam linhas de texto.
        numLines (int): O número de linhas a serem retornadas da lista `lines`. O padrão é 10.

    Retorna:
        list: Uma lista das primeiras linhas `numLines` da lista `lines`.
    """
    return lines[:numLines]


def argCount(line) -> int:
    """
    Calcula o número de argumentos na linha fornecida.

    Args:
        line (str): A linha de código a ser analisada.

    Retorna:
        int: O número de argumentos na linha.
    """
    args = getArgs(line)
    return len(args)


def eventArgLengthDictionary(lines) -> dict:
    """
    Dada uma lista de linhas, essa função cria um dicionário que mapeia os tipos de eventos para os comprimentos de seus respectivos argumentos.

    Parâmetros:
    - lines (lista): Uma lista de cadeias de caracteres que representam linhas de eventos.

    Retorna:
    - eventTypes (dict): Um dicionário que mapeia os tipos de eventos para os comprimentos de seus respectivos argumentos.
    """
    eventTypes = defaultdict(set)
    for line in lines:
        match = splitEvent(line)
        args = match.group(4).split(",")
        eventTypes[match.group(3)].add(len(args))
    return eventTypes


# Abre o arquivo de log
with open(
    "D:/Projetos_Git/dlLogs/scripts/logs/0050902dd75ac5836666d5cb41ff919e.txt"
) as file:
    # Lê o conteúdo do arquivo
    combatLog = file.read()
    # Divide o conteúdo em linhas
    lines = combatLog.splitlines()

    # Chama a função eventArgLengthDictionary para obter um dicionário com o comprimento dos argumentos de cada evento
    eventArgsLengthDict = eventArgLengthDictionary(lines)

    # Imprime o dicionário
    print(eventArgsLengthDict)

    # Itera sobre cada evento e seus comprimentos de argumentos no dicionário
    for event, lengths in eventArgsLengthDict.iteritems():
        lengthString = ""
        # Verifica se há mais de um comprimento de argumento para o evento
        if len(lengths) > 1:
            # Se houver, adiciona o menor e o maior comprimento à string
            lengthString += str(min(lengths)) + "-" + str(max(lengths))
        else:
            # Caso contrário, adiciona apenas o comprimento único
            lengthString += str(min(lengths))
        # Imprime o evento e o comprimento(s) de argumento(s)
        print(event + ": " + lengthString)

    # Comentado para evitar a execução do código
    # print((map(lambda x: splitEvent(x).groups()[1], peakLines(lines))))
