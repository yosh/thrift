from zope.interface import implements, Interface, Attribute
from twisted.internet.protocol import Protocol, ServerFactory, connectionDone
from twisted.protocols import basic
from twisted.python import log
from thrift.transport import TTransport
from cStringIO import StringIO


class TMessageSenderTransport(TTransport.TTransportBase):

    def __init__(self):
        self.__wbuf = StringIO()

    def write(self, buf):
        self.__wbuf.write(buf)

    def flush(self):
        msg = self.__wbuf.getvalue()
        self.__wbuf = StringIO()
        self.sendMessage(msg)

    def sendMessage(self, message):
        raise NotImplementedError

class TCallbackTransport(TMessageSenderTransport):

    def __init__(self, func):
        TMessageSenderTransport.__init__(self)
        self.func = func

    def sendMessage(self, message):
        self.func(message)

class ThriftClientProtocol(basic.Int32StringReceiver):

    def __init__(self, client_class, iprot_factory, oprot_factory=None):
        self._client_class = client_class
        self._iprot_factory = iprot_factory
        if oprot_factory is None:
            self._oprot_factory = iprot_factory
        else:
            self._oprot_factory = oprot_factory

        self.recv_map = {}

    def dispatch(self, msg):
        self.sendString(msg)

    def connectionMade(self):
        tmo = TCallbackTransport(self.dispatch)
        self.client = self._client_class(tmo, self._oprot_factory)

    def connectionLost(self, reason=connectionDone):
        for k,v in self.client._reqs.iteritems():
            tex = TTransport.TTransportException(
                type=TTransport.TTransportException.END_OF_FILE,
                message='Connection closed')
            v.errback(tex)

    def stringReceived(self, frame):
        tr = TTransport.TMemoryBuffer(frame)
        iprot = self._iprot_factory.getProtocol(tr)
        (fname, mtype, rseqid) = iprot.readMessageBegin()

        try:
            method = self.recv_map[fname]
        except KeyError:
            method = getattr(self.client, 'recv_' + fname)
            self.recv_map[fname] = method

        method(iprot, mtype, rseqid)


class ThriftServerProtocol(basic.Int32StringReceiver):

    def dispatch(self, msg):
        self.sendString(msg)

    def processError(self, error):
        self.transport.loseConnection()

    def processOk(self, _, tmo):
        msg = tmo.getvalue()

        if len(msg) > 0:
            self.dispatch(msg)

    def stringReceived(self, frame):
        tmi = TTransport.TMemoryBuffer(frame)
        tmo = TTransport.TMemoryBuffer()

        iprot = self.factory.iprot_factory.getProtocol(tmi)
        oprot = self.factory.oprot_factory.getProtocol(tmo)

        d = self.factory.processor.process(iprot, oprot)
        d.addCallbacks(self.processOk, self.processError,
            callbackArgs=(tmo,))


class IThriftServerFactory(Interface):

    processor = Attribute("Thrift processor")

    iprot_factory = Attribute("Input protocol factory")

    oprot_factory = Attribute("Output protocol factory")


class ThriftServerFactory(ServerFactory):

    implements(IThriftServerFactory)

    protocol = ThriftServerProtocol

    def __init__(self, processor, iprot_factory, oprot_factory=None):
        self.processor = processor
        self.iprot_factory = iprot_factory
        if oprot_factory is None:
            self.oprot_factory = iprot_factory
        else:
            self.oprot_factory = oprot_factory
