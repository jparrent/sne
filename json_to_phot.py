import json
import numpy as np
import matplotlib.pyplot as plt

file = raw_input('File to read:  ')

sn = file.split('.')[0]

f = open(file,'r')

data=json.load(f)

f.close()

lc = []

for i in data[sn]['photometry']:
    time = i['time']
    mag = i['magnitude']
    try: err = i['e_magnitude']
    except: err = 'nan'
    band = i['band']
    lc.append(np.array([time,mag,err,band]))

lc = np.array(lc)

filters = np.unique(lc[:,3])

filters = filters.tolist()

filtNames = ''

for i in filters:
    filtNames += '\t'+i+'\terr'

dates = np.unique(lc[:,0])


test = np.empty((len(dates),2*len(filters)+1))
test.fill(np.nan)

test[:,0] = dates

for i in test:
    for j in range(len(lc[:,0])):
        if float(lc[j,0])==i[0]:
            i[2*(filters.index(lc[j,3]))+1] = lc[j,1]
            i[2*(filters.index(lc[j,3]))+2] = lc[j,2]

lc_file = open(sn+'_lc.txt','w')

lc_file.write('#Time'+filtNames+'\n')

np.savetxt(lc_file,test,fmt='%.2f',delimiter='\t')

lc_file.close()


plt.figure(1)

plt.clf()

for i in range(len(filters)):
    plt.errorbar(test[:,0],test[:,2*i+1],fmt='o',label=filters[i])

plt.legend()

plt.gca().invert_yaxis()

plt.show()