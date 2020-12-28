# -*- coding: utf-8 -*-
import logging
from os.path import join

from hdx.data.dataset import Dataset
from hdx.utilities.path import temp_dir
from jsonpath_ng import parse
from olefile import olefile

from hdx.scraper import get_date_from_dataset_date, match_template

logger = logging.getLogger(__name__)


def get_url(url, **kwargs):
    for kwarg in kwargs:
        exec('%s="%s"' % (kwarg, kwargs[kwarg]))
    template_string, match_string = match_template(url)
    if template_string:
        replace_string = eval(match_string)
        url = url.replace(template_string, replace_string)
    return url


def read_tabular(downloader, datasetinfo, **kwargs):
    url = get_url(datasetinfo['url'], **kwargs)
    sheet = datasetinfo.get('sheet')
    headers = datasetinfo['headers']
    if isinstance(headers, list):
        kwargs['fill_merged_cells'] = True
    format = datasetinfo['format']
    compression = datasetinfo.get('compression')
    if compression:
        kwargs['compression'] = compression
    return downloader.get_tabular_rows(url, sheet=sheet, headers=headers, dict_form=True, format=format, **kwargs)


def read_ole(downloader, datasetinfo, **kwargs):
    url = get_url(datasetinfo['url'], **kwargs)
    with temp_dir('ole') as folder:
        path = downloader.download_file(url, folder, 'olefile')
        ole = olefile.OleFileIO(path)
        data = ole.openstream('Workbook').getvalue()
        outputfile = join(folder, 'excel_file.xls')
        with open(outputfile, 'wb') as f:
            f.write(data)
        datasetinfo['url'] = outputfile
        datasetinfo['format'] = 'xls'
        return read_tabular(downloader, datasetinfo, **kwargs)


def read_json(downloader, datasetinfo, **kwargs):
    url = get_url(datasetinfo['url'], **kwargs)
    response = downloader.download(url)
    json = response.json()
    expression = datasetinfo.get('jsonpath')
    if expression:
        expression = parse(expression)
        return expression.find(json)
    return json


def read_hdx_metadata(datasetinfo, today=None):
    dataset_name = datasetinfo['dataset']
    dataset = Dataset.read_from_hdx(dataset_name)
    format = datasetinfo['format']
    url = datasetinfo.get('url')
    if not url:
        for resource in dataset.get_resources():
            if resource['format'] == format.upper():
                url = resource['url']
                break
        if not url:
            logger.error('Cannot find %s resource in %s!' % (format, dataset_name))
            return None, None
        datasetinfo['url'] = url
    if 'date' not in datasetinfo:
        datasetinfo['date'] = get_date_from_dataset_date(dataset, today=today)
    if 'source' not in datasetinfo:
        datasetinfo['source'] = dataset['dataset_source']
    if 'source_url' not in datasetinfo:
        datasetinfo['source_url'] = dataset.get_hdx_url()


def read_hdx(downloader, datasetinfo, today=None):
    read_hdx_metadata(datasetinfo, today=today)
    return read_tabular(downloader, datasetinfo)


def read(downloader, name, datasetinfo, today=None, **kwargs):
    format = datasetinfo['format']
    if format == 'json':
        lst = read_json(downloader, datasetinfo, **kwargs)
        iterator = iter(lst)
        headers = None
    elif format == 'ole':
        headers, iterator = read_ole(downloader, datasetinfo, **kwargs)
    elif format in ['csv', 'xls', 'xlsx']:
        if 'dataset' in datasetinfo:
            headers, iterator = read_hdx(downloader, datasetinfo, today=today)
        else:
            headers, iterator = read_tabular(downloader, datasetinfo, **kwargs)
    else:
        raise ValueError('Invalid format %s for %s!' % (format, name))
    return headers, iterator
