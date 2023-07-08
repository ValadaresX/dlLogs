import re
from collections import defaultdict


def getEventType(line: str) -> str:
    return line.split("  ")[1].split(",")[0]


def getAllUniqueEventTypes(lines):
    events = set(map(getEventType, lines))
    return events


def getArgs(line):
    return line.split("  ")[1].split(",")[1:]


def splitEvent(line):
    pattern = re.compile(r"(\d\/\d+)\s(\d+\:\d+\:\d+\.\d+)\s\s(\w+),(.+)")
    return pattern.match(line)


def peakLines(lines, numLines=10):
    return lines[:numLines]


def argCount(line):
    args = getArgs(line)
    return len(args)


def eventArgLengthDictionary(lines):
    eventTypes = defaultdict(set)
    for line in lines:
        match = splitEvent(line)
        args = match.group(4).split(",")
        eventTypes[match.group(3)].add(len(args))
    return eventTypes


with open("D:\\Projetos_Git\\dlLogs\\scripts\\testando.txt") as file:
    combatLog = file.read()
    combatLog = re.sub(r"\n\s*\n", "\n", combatLog)  # remove linhas vazias

    lines = combatLog.splitlines()

    eventArgsLengthDict = eventArgLengthDictionary(lines)
    print(eventArgsLengthDict)
    for event, lengths in eventArgsLengthDict.items():
        lengthString = ""
        if len(lengths) > 1:
            lengthString += str(min(lengths)) + "-" + str(max(lengths))
        else:
            lengthString += str(min(lengths))
        print(event + ": " + lengthString)
    # print((map(lambda x: splitEvent(x).groups()[1], peakLines(lines))))
