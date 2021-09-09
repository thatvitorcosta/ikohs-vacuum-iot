from Ikohs import *
import time

i = Ikohs({'username': 'vitor2877@gmail.com', 'password': 'Muhamed2877'})
v = i.getVacuum()
i.doAction(v['thingId'], 'start')
time.sleep(20)
i.doAction(v['thingId'], 'returnHome')