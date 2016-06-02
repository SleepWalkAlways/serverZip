from serverZip import ParseServerZip



if __name__ == '__main__':
    url = ''
    parse = ParseServerZip(url)
    toc = parse.getTableOfContents()
    print(toc)

    data = parse.extractFile(b'AndroidManifest.xml')

