
__author__="Jack Chan"
__date__ ="2016-6-2 15:15:15"


__version__ = "0.0.1"

"""Support module for extract zip (Common Gateway Interface) scripts.

This module defines a number of utilities for use by ParseServerZip scripts
written in Python3.x.
"""


import sys

if sys.version < '3':
    raise EnvironmentError('please check python version is 3.x')




import time
import re
import os
import requests
from struct import unpack
import zlib


class ParseServerZip:

    def __init__(self, url):

        if not isinstance(url, str):
            raise ValueError('url must be an str!')

        self._url = url
        self.filesize = None
        self.start = None
        self.end = None
        self.directory_end = None
        self.raw_bytes = None
        self.directory_size = None
        self.tableOfContents = None



    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, value):
        if not isinstance(value, str):
            raise ValueError('url must be an str!')
        self._url = value


    def requestContentDirectory(self):
        self.start = self.filesize - 1048576
        self.end = self.filesize - 1
        headers = {}
        headers['Range'] = "bytes=%d-%d" % (self.start, self.end)
        handle = requests.get(self._url, headers=headers)

        # got here? we're fine, read the contents
        self.raw_bytes = handle.content

        self.directory_end = self.raw_bytes.find(b"\x50\x4b\x05\x06")


    def __file_exists(self):
        # check if file exists
        try:
            headRequest = requests.head(self._url)
            self.filesize = int(headRequest.headers['Content-Length'])
            if 'Accept-Ranges' not in headRequest.headers:
                raise NotSupportException('request is not support Range')
            return True
        except Exception as e:
            print (e)
            return False

    def getDirectorySize(self):
        if not self.__file_exists():
            raise NotSupportException('file is not support Range')

        # now request bytes from that size minus a 64kb max zip directory length
        self.start = self.filesize - (65536)
        self.end = self.filesize - 1
        headers = {}
        headers['Range'] = "bytes=%d-%d" % (self.start, self.end)
        handle = requests.get(self.url, headers=headers)
        # got here? we're fine, read the contents
        self.raw_bytes = handle.content

        # now find the end-of-directory: 06054b50
        # we're on little endian maybe
        self.directory_end = self.raw_bytes.find(b"\x50\x4b\x05\x06")
        if self.directory_end < 0:
            raise NotSupportException("Could not find end of directory")

        # now find the size of the directory: offset 12, 4 bytes
        self.directory_size = unpack("i", self.raw_bytes[self.directory_end+12:self.directory_end+16])[0]

        return self.directory_size

    def getTableOfContents(self):
        """
        This function populates the internal tableOfContents list with the contents
        of the zip file TOC.
        """

        self.directory_size = self.getDirectorySize()

        if self.directory_size > 65536:
            self.requestContentDirectory()


        # and find the offset from start of file where it can be found
        directory_start = unpack("i", self.raw_bytes[self.directory_end + 16: self.directory_end + 20])[0]
        # find the data in the raw_bytes
        self.raw_bytes = self.raw_bytes
        current_start = directory_start - self.start
        filestart = 0
        compressedsize = 0
        tableOfContents = []

        try:
            while True:
                # get file name size (n), extra len (m) and comm len (k)
                zip_n = unpack("H", self.raw_bytes[current_start + 28: current_start + 28 + 2])[0]
                zip_m = unpack("H", self.raw_bytes[current_start + 30: current_start + 30 + 2])[0]
                zip_k = unpack("H", self.raw_bytes[current_start + 32: current_start + 32 + 2])[0]
                

                filename = self.raw_bytes[current_start + 46: current_start + 46 + zip_n]

                # check if this is the index file
                filestart = unpack("I", self.raw_bytes[current_start + 42: current_start + 42 + 4])[0]
                compressedsize = unpack("I", self.raw_bytes[current_start + 20: current_start + 20 + 4])[0]
                uncompressedsize = unpack("I", self.raw_bytes[current_start + 24: current_start + 24 + 4])[0]
                tableItem = {
                    'filename': filename,
                    'compressedsize': compressedsize,
                    'uncompressedsize': uncompressedsize,
                    'filestart': filestart
                }
                tableOfContents.append(tableItem)

                # not this file, move along
                current_start = current_start + 46 + zip_n + zip_m + zip_k
        except:
            pass

        self.tableOfContents = tableOfContents
        return tableOfContents


    def extractFile(self, filename):
        """
        This function will extract a single file from the remote zip without downloading
        the entire zip file. The filename argument should match whatever is in the 'filename'
        key of the tableOfContents.
        """
        files = [x for x in self.tableOfContents if x['filename'] == filename]
        if len(files) == 0:
            raise Exception('File is not exists')

        fileRecord = files[0]

        # got here? need to fetch the file size
        metaheadroom = 1024  # should be enough
        end = fileRecord['filestart'] + fileRecord['compressedsize'] + metaheadroom
        headers = {}
        headers['Range'] = "bytes=%d-%d" % (fileRecord['filestart'], end)
        handle = requests.get(self._url, headers=headers)

        # got here? we're fine, read the contents
        filedata = handle.content

        # find start of raw file data
        zip_n = unpack("H", filedata[26:28])[0]
        zip_m = unpack("H", filedata[28:30])[0]

        # check compressed size
        comp_size = unpack("I", filedata[18:22])[0]
        if comp_size != fileRecord['compressedsize']:
            raise Exception("Something went wrong. Directory and file header disagree of compressed file size")

        raw_zip_data = filedata[30 + zip_n + zip_m: 30 + zip_n + zip_m + comp_size]
        uncompressed_data = ""
        # can't decompress if stored without compression
        compression_method = unpack("H", filedata[8:10])[0]
        if compression_method == 0:
          return raw_zip_data

        dec = zlib.decompressobj(-zlib.MAX_WBITS)
        uncompressed_data = dec.decompress(raw_zip_data)
        return uncompressed_data


class NotSupportException(Exception):
    pass


    