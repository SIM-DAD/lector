# Stub package - satisfies chatterbox-tts dependency.
# pkuseg is only used for Chinese text segmentation.
# For English-only use this stub is sufficient.

class pkuseg:
    def __init__(self, *args, **kwargs):
        pass

    def cut(self, text):
        return text.split()
