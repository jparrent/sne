#!/usr/local/bin/python3.5

import csv
import glob
import sys
import os
import re
import operator
import json
import argparse
from datetime import datetime
#from colorpy.ciexyz import xyz_from_wavelength
#from colorpy.colormodels import irgb_string_from_xyz
from copy import deepcopy
from random import shuffle, seed
from collections import OrderedDict
from bokeh.io import hplot, vplot, gridplot
from bokeh.plotting import Figure, show, save, ColumnDataSource
from bokeh.models import HoverTool
from bokeh.resources import CDN
from bokeh.embed import file_html

parser = argparse.ArgumentParser(description='Generate a catalog JSON file and plot HTML files from SNE data.')
parser.add_argument('--no-write-catalog', '-wc', dest='writecatalog', help='write catalog file',    default=True,  action='store_false')
parser.add_argument('--no-write-html', '-wh',    dest='writehtml',    help='write html plot files', default=True,  action='store_false')
parser.add_argument('--test', '-t',              dest='test',         help='test this script',      default=False, action='store_true')
args = parser.parse_args()

outdir = "../"

testsuffix = '.test' if args.test else ''

columnkey = [
    "check",
    "name",
    "aliases",
    "discoverdate",
    "maxdate",
    "maxappmag",
    "maxabsmag",
    "host",
    "instruments",
    "redshift",
    "hvel",
    "lumdist",
    "claimedtype",
    "data",
    "responsive"
]

header = [
    "",
    "Name",
    "Aliases",
    "Discovery Date",
    "Date of Max",
    r"<em>m</em><sub>max</sub>",
    r"<em>M</em><sub>max</sub>",
    "Host Name",
    "Instruments/Bands",
    r"<em>z</em>",
    r"<em>v</em><sub>&#9737;</sub> (km/s)",
    r"<em>d</e><sub>L</sub> (Mpc)",
    "Claimed Type",
    "Data",
    ""
]

photokeys = [
    'timeunit',
    'time',
    'band',
    'instrument',
    'abmag',
    'aberr',
    'upperlimit',
    'source'
]

sourcekeys = [
    'name',
    'alias',
    'secondary'
]

repfolders = [
    'sne-pre-1990',
    'sne-1990-1999',
    'sne-2000-2004',
    'sne-2005-2009',
    'sne-2010-2014',
    'sne-2015-2019'
]

repyears = [int(repfolders[x][-4:]) for x in range(len(repfolders))]

if len(columnkey) != len(header):
    print('Error: Header not same length as key list.')
    sys.exit(0)

dataavaillink = "<a href='https://bitbucket.org/Guillochon/sne'>Y</a>";

header = OrderedDict(list(zip(columnkey,header)))

bandcodes = [
    "u",
    "g",
    "r",
    "i",
    "z",
    "u'",
    "g'",
    "r'",
    "i'",
    "z'",
    "u_SDSS",
    "g_SDSS",
    "r_SDSS",
    "i_SDSS",
    "z_SDSS",
    "U",
    "B",
    "V",
    "R",
    "I",
    "G",
    "Y",
    "J",
    "H",
    "K",
    "C",
    "CR",
    "CV"
]

bandaliases = {
    "u_SDSS" : "u (SDSS)",
    "g_SDSS" : "g (SDSS)",
    "r_SDSS" : "r (SDSS)",
    "i_SDSS" : "i (SDSS)",
    "z_SDSS" : "z (SDSS)"
}

bandshortaliases = {
    "u_SDSS" : "u",
    "g_SDSS" : "g",
    "r_SDSS" : "r",
    "i_SDSS" : "i",
    "z_SDSS" : "z",
    "G" : ""
}

bandwavelengths = {
    "u" : 354.,
    "g" : 475.,
    "r" : 622.,
    "i" : 763.,
    "z" : 905.,
    "u'" : 354.,
    "g'" : 475.,
    "r'" : 622.,
    "i'" : 763.,
    "z'" : 905.,
    "u_SDSS" : 354.3,
    "g_SDSS" : 477.0,
    "r_SDSS" : 623.1,
    "i_SDSS" : 762.5,
    "z_SDSS" : 913.4,
    "U" : 365.,
    "B" : 445.,
    "V" : 551.,
    "R" : 658.,
    "I" : 806.,
    "Y" : 1020.,
    "J" : 1220.,
    "H" : 1630.,
    "K" : 2190.
}

wavedict = dict(list(zip(bandcodes,bandwavelengths)))

seed(101)
bandcolors = ["#%06x" % round(float(x)/float(len(bandcodes))*0xFFFEFF) for x in range(len(bandcodes))]
shuffle(bandcolors)

def event_filename(name):
    return(name.replace('/', '_'))

# Replace bands with real colors, if possible.
#for b, code in enumerate(bandcodes):
#    if (code in bandwavelengths):
#        hexstr = irgb_string_from_xyz(xyz_from_wavelength(bandwavelengths[code]))
#        if (hexstr != "#000000"):
#            bandcolors[b] = hexstr

bandcolordict = dict(list(zip(bandcodes,bandcolors)))

coldict = dict(list(zip(list(range(len(columnkey))),columnkey)))

def bandcolorf(color):
    if (color in bandcolordict):
        return bandcolordict[color]
    return 'black'

def bandaliasf(code):
    if (code in bandaliases):
        return bandaliases[code]
    return code

def bandshortaliasf(code):
    if (code in bandshortaliases):
        return bandshortaliases[code]
    return code

def bandwavef(code):
    if (code in bandwavelengths):
        return bandwavelengths[code]
    return 0.

def utf8(x):
    return str(x, 'utf-8')

def get_rep_folder(entry):
    if 'discoveryear' not in entry:
        return repfolders[0]
    if not is_number(entry['discoveryear']):
        print ('Error, discovery year is not a number!')
        sys.exit()
    for r, repyear in enumerate(repyears):
        if int(entry['discoveryear']) <= repyear:
            return repfolders[r]
    return repfolders[0]

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False

catalog = OrderedDict()
catalogcopy = OrderedDict()
snepages = []
sourcedict = dict()
nophoto = []

files = []
for rep in repfolders:
    files += glob.glob('../' + rep + "/*.json")

for fcnt, file in enumerate(sorted(files, key=lambda s: s.lower())):
    print(file)
    filehead, ext = os.path.splitext(file)

    f = open(file, 'r')
    filetext = f.read()
    f.close()

    catalog.update(json.loads(filetext, object_pairs_hook=OrderedDict))
    entry = next(reversed(catalog))

    eventname = entry

    catalog[entry]['data'] = "<span class='ics'>"
    repfolder = get_rep_folder(catalog[entry])
    catalog[entry]['data'] += "<a class='dci' href='https://raw.githubusercontent.com/astrotransients/" + repfolder + "/" + eventname + ".json' download></a>"
    photoavail = True if len(catalog[entry]['photometry']) else False
    catalog[entry]['numphoto'] = len(catalog[entry]['photometry'])
    if photoavail:
        plotlink = "sne/" + eventname + ".html";
        catalog[entry]['photoplot'] = plotlink
        plotlink = "<a class='lci' href='" + plotlink + "' target='_blank'></a>";
        catalog[entry]['data'] += plotlink
    spectraavail = True if len(catalog[entry]['spectra']) else False
    catalog[entry]['numspectra'] = len(catalog[entry]['spectra'])
    if spectraavail:
        plotlink = "sne/" + eventname + ".html";
        catalog[entry]['spectraplot'] = plotlink
        plotlink = "<a class='sci' href='" + plotlink + "' target='_blank'></a>";
        catalog[entry]['data'] += plotlink
    if photoavail:
        catalog[entry]['data'] += " " + str(len(catalog[entry]['photometry']))
    if spectraavail:
        catalog[entry]['data'] += " (" + str(len(catalog[entry]['spectra'])) + ")"
    catalog[entry]['data'] += "</span>"
    
    prange = list(range(catalog[entry]['numphoto']))
    instrulist = sorted([_f for _f in list({catalog[entry]['photometry'][x]['instrument'] if 'instrument' in catalog[entry]['photometry'][x] else None for x in prange}) if _f])
    if len(instrulist) > 0:
        instruments = ''
        for i, instru in enumerate(instrulist):
            instruments += instru
            bandlist = sorted([_f for _f in list({bandshortaliasf(catalog[entry]['photometry'][x]['band'])
                if 'instrument' in catalog[entry]['photometry'][x] and catalog[entry]['photometry'][x]['instrument'] == instru else "" for x in prange}) if _f], key=lambda y: bandwavef(y))
            if bandlist:
                instruments += ' (' + ", ".join(bandlist) + ')'
            if i < len(instrulist) - 1:
                instruments += ', '

        catalog[entry]['instruments'] = instruments
    else:
        bandlist = sorted([_f for _f in list({bandshortaliasf(catalog[entry]['photometry'][x]['band']) for x in prange}) if _f], key=lambda y: bandwavef(y))
        if len(bandlist) > 0:
            catalog[entry]['instruments'] = ", ".join(bandlist)

    tools = "pan,wheel_zoom,box_zoom,save,crosshair,reset,resize"

    # Construct the date
    discoverdatestr = ''
    if 'discoveryear' in catalog[entry]:
        discoverdatestr += str(catalog[entry]['discoveryear'])
        if 'discovermonth' in catalog[entry]:
            discoverdatestr += '-' + str(catalog[entry]['discovermonth']).zfill(2)
            if 'discoverday' in catalog[entry]:
                discoverdatestr += '-' + str(catalog[entry]['discoverday']).zfill(2)
    catalog[entry]['discoverdate'] = discoverdatestr

    maxdatestr = ''
    if 'maxyear' in catalog[entry]:
        maxdatestr += str(catalog[entry]['maxyear'])
        if 'maxmonth' in catalog[entry]:
            maxdatestr += '-' + str(catalog[entry]['maxmonth']).zfill(2)
            if 'maxday' in catalog[entry]:
                maxdatestr += '-' + str(catalog[entry]['maxday']).zfill(2)

    catalog[entry]['maxdate'] = maxdatestr

    # Check file modification times before constructing .html files, which is expensive
    dohtml = True
    if (photoavail or spectraavail) and os.path.isfile(outdir + eventname + ".html"):
            t1 = datetime.fromtimestamp(os.path.getmtime(filehead + ".json"))
            t2 = datetime.fromtimestamp(os.path.getmtime(outdir + eventname + ".html"))
            if t1 < t2:
                dohtml = False

    if photoavail and dohtml and args.writehtml:
        phototime = [float(catalog[entry]['photometry'][x]['time']) for x in prange]
        photoAB = [float(catalog[entry]['photometry'][x]['abmag']) for x in prange]
        photoerrs = [float(catalog[entry]['photometry'][x]['aberr']) if 'aberr' in catalog[entry]['photometry'][x] else 0. for x in prange]
        photoband = [catalog[entry]['photometry'][x]['band'] for x in prange]
        photoinstru = [catalog[entry]['photometry'][x]['instrument'] if 'instrument' in catalog[entry]['photometry'][x] else '' for x in prange]
        photosource = [', '.join(str(j) for j in sorted(int(i) for i in catalog[entry]['photometry'][x]['source'].split(','))) for x in prange]
        phototype = [bool(catalog[entry]['photometry'][x]['upperlimit']) if 'upperlimit' in catalog[entry]['photometry'][x] else False for x in prange]

        x_buffer = 0.1*(max(phototime) - min(phototime)) if len(phototime) > 1 else 1.0
        x_range = [-x_buffer + min(phototime), x_buffer + max(phototime)]

        tt = [  
                ("Source ID", "@src"),
                ("MJD", "@x{1.11}"),
                ("Magnitude", "@y{1.111}"),
                ("Error", "@err{1.111}"),
                ("Band", "@desc")
             ]
        if len(list(filter(None, photoinstru))):
            tt += [("Instrument", "@instr")]
        hover = HoverTool(tooltips = tt)

        p1 = Figure(title='Photometry for ' + eventname, x_axis_label='Time (' + catalog[entry]['photometry'][0]['timeunit'] + ')',
            y_axis_label='AB Magnitude', x_range = x_range, tools = tools,
            y_range = (0.5 + max([x + y for x, y in list(zip(photoAB, photoerrs))]), -0.5 + min([x - y for x, y in list(zip(photoAB, photoerrs))])))
        p1.add_tools(hover)

        err_xs = []
        err_ys = []

        for x, y, yerr in list(zip(phototime, photoAB, photoerrs)):
            err_xs.append((x, x))
            err_ys.append((y - yerr, y + yerr))

        bandset = set(photoband)
        bandset = [i for (j, i) in sorted(list(zip(list(map(bandaliasf, bandset)), bandset)))]

        for band in bandset:
            bandname = bandaliasf(band)
            indb = [i for i, j in enumerate(photoband) if j == band]
            indt = [i for i, j in enumerate(phototype) if j == 0]
            ind = set(indb).intersection(indt)

            source = ColumnDataSource(
                data = dict(
                    x = [phototime[i] for i in ind],
                    y = [photoAB[i] for i in ind],
                    err = [photoerrs[i] for i in ind],
                    desc = [photoband[i] for i in ind],
                    instr = [photoinstru[i] for i in ind],
                    src = [photosource[i] for i in ind]
                )
            )
            p1.circle('x', 'y', source = source, color=bandcolorf(band), legend=bandname, size=4)
            p1.multi_line([err_xs[x] for x in ind], [err_ys[x] for x in ind], color=bandcolorf(band))

            upplimlegend = bandname if len(ind) == 0 else ''

            indt = [i for i, j in enumerate(phototype) if j == 1]
            ind = set(indb).intersection(indt)
            p1.inverted_triangle([phototime[x] for x in ind], [photoAB[x] for x in ind],
                color=bandcolorf(band), legend=upplimlegend, size=7)

    if spectraavail and dohtml and args.writehtml:
        spectrumwave = []
        spectrumflux = []
        spectrumerrs = []
        for spectrum in catalog[entry]['spectra']:
            specrange = range(len(spectrum['data']))
            spectrumwave.append([float(spectrum['data'][x][0]) for x in specrange])
            spectrumflux.append([float(spectrum['data'][x][1]) for x in specrange])
            if spectrum['errorunit']:
                spectrumerrs.append([float(spectrum['data'][x][2]) for x in specrange])
        
        y_height = 0.
        for i in range(len(spectrumwave)):
            ydiff = 0.8*max(spectrumflux[i]) - min(spectrumflux[i])
            spectrumflux[i] = [j + y_height for j in spectrumflux[i]]
            y_height += ydiff

        maxsw = max(map(max, spectrumwave))
        minsw = min(map(min, spectrumwave))
        maxfl = max(map(max, spectrumflux))
        minfl = min(map(min, spectrumflux))
        maxfldiff = max(map(operator.sub, list(map(max, spectrumflux)), list(map(min, spectrumflux))))
        x_buffer = 0.0 #0.1*(maxsw - minsw)
        x_range = [-x_buffer + minsw, x_buffer + maxsw]
        y_buffer = 0.1*maxfldiff
        y_range = [-y_buffer + minfl, y_buffer + maxfl]

        p2 = Figure(title='Spectra for ' + eventname, x_axis_label='Wavelength (' + catalog[entry]['spectra'][0]['waveunit'] + ')',
            y_axis_label='Flux (' + catalog[entry]['spectra'][0]['fluxunit'] + ')' + ' + offset'
            if (len(catalog[entry]['spectra']) > 1) else '', x_range = x_range, tools = tools,
            y_range = y_range)

        for i in range(len(spectrumwave)):
            p2.line(x = spectrumwave[i], y = spectrumflux[i])

    if (photoavail or spectraavail) and dohtml and args.writehtml:
        if photoavail and spectraavail:
            p = gridplot([[p1, p2]])
        elif photoavail:
            p = p1
        else:
            p = p2

        html = file_html(p, CDN, eventname)
        returnlink = r'    <br><a href="https://sne.space"><< Return to supernova catalog</a>';
        repfolder = get_rep_folder(catalog[entry])
        html = re.sub(r'(\<\/body\>)', r'    <a href="https://raw.githubusercontent.com/astrotransients/' + repfolder + '/' + eventname + r'.json" download>Download datafile</a><br><br>\n        \1', html)
        if len(catalog[entry]['sources']):
            html = re.sub(r'(\<\/body\>)', r'<em>Sources of data:</em><br><table><tr><th width=30px>ID</th><th>Source</th></tr>\n        \1', html)
            for source in catalog[entry]['sources']:
                html = re.sub(r'(\<\/body\>)', r'<tr><td>' + source['alias'] +
                r'</td><td>' + source['name'].encode('ascii', 'xmlcharrefreplace').decode("utf-8") +
                r'</td></tr>\n        \1', html)
            html = re.sub(r'(\<\/body\>)', r'</table>\n    \1', html)
        html = re.sub(r'(\<\/body\>)', returnlink+r'\n    \1', html)
        print(outdir + eventname + ".html")
        with open(outdir + eventname + ".html", "w") as f:
            f.write(html)

    #if fcnt > 100:
    #    sys.exit()

    # Save this stuff because next line will delete it.
    if args.writecatalog:
        if 'photoplot' in catalog[entry]:
            snepages.append(catalog[entry]['aliases'] + ['https://sne.space/' + catalog[entry]['photoplot']])

        for sourcerow in catalog[entry]['sources']:
            strippedname = re.sub('<[^<]+?>', '', sourcerow['name'].encode('ascii','xmlcharrefreplace').decode("utf-8"))
            if strippedname in sourcedict:
                sourcedict[strippedname] += 1
            else:
                sourcedict[strippedname] = 1

        nophoto.append(catalog[entry]['numphoto'] < 3)

        # Delete unneeded data from catalog, add blank entries when data missing.
        catalogcopy[entry] = OrderedDict()
        for col in columnkey:
            if col in catalog[entry]:
                catalogcopy[entry][col] = catalog[entry][col]
            else:
                catalogcopy[entry][col] = None

    if args.test and spectraavail and photoavail:
        break

# Write it all out at the end
if args.writecatalog:
    # Make a few small files for generating charts
    f = open(outdir + 'snepages.csv' + testsuffix, 'w')
    csvout = csv.writer(f, quotechar='"', quoting=csv.QUOTE_ALL)
    for row in snepages:
        csvout.writerow(row)
    f.close()

    f = open(outdir + 'sources.csv' + testsuffix, 'w')
    sortedsources = sorted(list(sourcedict.items()), key=operator.itemgetter(1), reverse=True)
    csvout = csv.writer(f)
    csvout.writerow(['Source','Number'])
    for source in sortedsources:
        csvout.writerow(source)
    f.close()

    nophoto = sum(nophoto)
    hasphoto = len(catalog) - nophoto
    f = open(outdir + 'pie.csv' + testsuffix, 'w')
    csvout = csv.writer(f)
    csvout.writerow(['Category','Number'])
    csvout.writerow(['Has light curve', hasphoto])
    csvout.writerow(['No light curve', nophoto])
    f.close()
    f = open(outdir + 'hasphoto.html' + testsuffix, 'w')
    f.write(str(hasphoto))
    f.close()
    f = open(outdir + 'snecount.html' + testsuffix, 'w')
    f.write(str(len(catalog)))
    f.close()

    ctypedict = dict()
    for entry in catalog:
        cleanedtype = ''
        if 'claimedtype' in catalog[entry]:
            cleanedtype = catalog[entry]['claimedtype'].strip('?* ')
            cleanedtype = cleanedtype.replace('Ibc', 'Ib/c')
            cleanedtype = cleanedtype.replace('IIP', 'II P')
        if not cleanedtype:
            cleanedtype = 'Unknown'
        if cleanedtype in ctypedict:
            ctypedict[cleanedtype] += 1
        else:
            ctypedict[cleanedtype] = 1
    sortedctypes = sorted(list(ctypedict.items()), key=operator.itemgetter(1), reverse=True)
    f = open(outdir + 'types.csv' + testsuffix, 'w')
    csvout = csv.writer(f)
    csvout.writerow(['Type','Number'])
    for ctype in sortedctypes:
        csvout.writerow(ctype)
    f.close()

    catalog = catalogcopy

    # Convert to array since that's what datatables expects
    catalog = list(catalog.values())

    jsonobj = dict.fromkeys(['data'])
    jsonobj['data'] = catalog
    #jsonstring = json.dumps(jsonobj, indent=4, separators=(',', ': '))
    jsonstring = json.dumps(jsonobj, separators=(',',':'))
    f = open(outdir + 'sne-catalog.json' + testsuffix, 'w')
    f.write(jsonstring)
    f.close()

    f = open(outdir + 'catalog.html' + testsuffix, 'w')
    f.write('<table id="example" class="display" cellspacing="0" width="100%">\n')
    f.write('\t<thead>\n')
    f.write('\t\t<tr>\n')
    for h in header:
        f.write('\t\t\t<th class="' + h + '">' + header[h] + '</th>\n')
    f.write('\t\t</tr>\n')
    f.write('\t</thead>\n')
    f.write('\t<tfoot>\n')
    f.write('\t\t<tr>\n')
    for h in header:
        f.write('\t\t\t<th>' + header[h] + '</th>\n')
    f.write('\t\t</tr>\n')
    f.write('\t</thead>\n')
    f.write('</table>\n')
    f.close()
