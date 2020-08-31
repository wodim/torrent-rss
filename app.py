from datetime import datetime
import json
from urllib.parse import urlparse, quote

from bs4 import BeautifulSoup
from dateutil import tz
from feedgen.feed import FeedGenerator
from flask import abort, Flask, request, Response
import requests

from parallel import Parallel


app = Flask(__name__)


@app.route('/', methods=('GET',))
def index():
    url = request.args.get('url')
    if not url:
        abort(404)
    if urlparse(url).netloc not in ('apibay.org', '1337x.to'):
        abort(403)

    fg = FeedGenerator()
    fg.id(url)
    fg.title('Feed: ' + url)
    fg.description('RSS feed for ' + url)
    fg.link(href=':-)')

    if urlparse(url).netloc == 'apibay.org':
        torrents = json.loads(requests.get(url).content)

        for torrent in sorted(torrents, key=lambda x: int(x['added'])):
            fe = fg.add_entry()
            fe.id(torrent['info_hash'])
            fe.link(href=('magnet:?xt=urn:btih:' + torrent['info_hash'] +
                          '&dn=' + quote(torrent['name'])))
            fe.description(torrent['name'])
            fe.title(torrent['name'])
            fe.published(datetime.fromtimestamp(int(torrent['added']),
                         tz=tz.tzutc()))
    elif urlparse(url).netloc == '1337x.to':
        def magnet_extract(queue):
            while True:
                id_, link, name = queue.get()
                html = requests.get(link).content
                soup = BeautifulSoup(html)
                magnet = soup.select('a[href^="magnet:"]')[0]['href']
                infohash = magnet[20:20+40]
                r.append((id_, name, infohash, magnet))
                queue.task_done()

        html = requests.get(url).content
        soup = BeautifulSoup(html)
        torrents = [(int(x['href'].split('/')[2]),
                     'https://1337x.to' + x['href'],
                     x.get_text())
                    for x in soup.select('a[href^="/torrent/"]')]
        r = []
        parallel = Parallel(magnet_extract, torrents, 32)
        parallel.start()

        for id_, name, infohash, magnet in sorted(r, key=lambda x: x[0]):
            fe = fg.add_entry()
            fe.id(infohash)
            fe.link(href=magnet)
            fe.description(name)
            fe.title(name)
            # it's made up so I don't have to parse it, but it's unique
            fe.published(datetime.fromtimestamp(1590000000 + id_,
                                                tz=tz.tzutc()))

    return Response(fg.rss_str(), mimetype='application/rss+xml')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=55500, debug=True)
