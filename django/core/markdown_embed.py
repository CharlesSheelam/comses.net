# FIXME: this may not make a whole lot of sense sitting in the root of core,
# finnd out elsewhere to put this
import logging

from markdown import Extension
from markdown.inlinepatterns import InlineProcessor
import xml.etree.ElementTree as etree

logger = logging.getLogger(__name__)

PROVIDERS = {
  "youtube": {
    "re": r'youtube\.com/watch\?\S*v=(?P<youtube>[A-Za-z0-9_&=-]+)',
    "embed": "//www.youtube.com/embed/%s"
  },
  "vimeo": {
    "re": r'vimeo\.com/(?P<vimeo>\d+)',
    "embed": "//player.vimeo.com/video/%s"
  }
}

VIDEO_PATTERN = r'\!\[(?P<alt>[^\]]*)\]\((https?://(www\.|)({0}|{1})\S*)' \
                 r'(?<!png)(?<!jpg)(?<!jpeg)(?<!gif)\)'\
                  .format(PROVIDERS["youtube"]["re"], PROVIDERS["vimeo"]["re"])

class VideoEmbedExtension(Extension):
  """
  Embed videos in markdown by using ![alt text](url), supports youtube and vimeo
  """
  def extendMarkdown(self, md):
    link_pattern = VideoEmbedInlineProcessor(VIDEO_PATTERN, md)
    # priority level 175 is a total guess, shouldn't run into any issues with img's though
    md.inlinePatterns.register(link_pattern, "video_embed", 175)

class VideoEmbedInlineProcessor(InlineProcessor):
  def handleMatch(self, m, data):
    el = None
    alt = m.group("alt").strip()
    for provider in PROVIDERS.keys():
      video_id = m.group(provider)
      if video_id:
        el = self.create_el(provider, video_id, alt)
    return el, m.start(0), m.end(0)

  def create_el(self, provider, video_id, alt):
    el = etree.Element("iframe")
    el.set("class", provider)
    el.set("src", PROVIDERS[provider]["embed"] % video_id.strip())
    el.set("alt", alt)
    el.set("allowfullscreen", "true")
    return el
