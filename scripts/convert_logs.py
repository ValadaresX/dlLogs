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
    return line.split("  ")[1].split(",")[1:]


def splitEvent(line) -> re.Match:
    pattern = re.compile(r"(\d\/\d+)\s(\d+\:\d+\:\d+\.\d+)\s\s(\w+),(.+)")
    return pattern.match(line)


def peakLines(lines, numLines=10) -> list:
    return lines[:numLines]


def argCount(line) -> int:
    args = getArgs(line)
    return len(args)


def eventArgLengthDictionary(lines) -> dict:
    eventTypes = defaultdict(set)
    for line in lines:
        match = splitEvent(line)
        args = match.group(4).split(",")
        eventTypes[match.group(3)].add(len(args))
    return eventTypes


with open(
    "D:/Projetos_Git/dlLogs/scripts/logs/0050902dd75ac5836666d5cb41ff919e.txt"
) as file:
    combatLog = file.read()
    lines = combatLog.splitlines()
    eventArgsLengthDict = eventArgLengthDictionary(lines)
    print(eventArgsLengthDict)
    for event, lengths in eventArgsLengthDict.iteritems():
        lengthString = ""
        if len(lengths) > 1:
            lengthString += str(min(lengths)) + "-" + str(max(lengths))
        else:
            lengthString += str(min(lengths))
        print(event + ": " + lengthString)
    # print((map(lambda x: splitEvent(x).groups()[1], peakLines(lines))))
