# Written by S. Mevawala, modified by D. Gitzel
import copy
import logging
import socket

import channelsimulator
import utils
import sys


class Sender(object):

    def __init__(self, inbound_port=50006, outbound_port=50005, timeout=10, debug_level=logging.INFO):
        self.logger = utils.Logger(self.__class__.__name__, debug_level)

        self.inbound_port = inbound_port
        self.outbound_port = outbound_port
        self.simulator = channelsimulator.ChannelSimulator(inbound_port=inbound_port, outbound_port=outbound_port,
                                                           debug_level=debug_level)
        self.simulator.sndr_setup(timeout)
        self.simulator.rcvr_setup(timeout)

    def send(self, data):
        raise NotImplementedError("The base API class has no implementation. Please override and add your own.")


class BogoSender(Sender):

    def __init__(self):
        super(BogoSender, self).__init__()

    def send(self, data):
        self.logger.info(
            "Sending on port: {} and waiting for ACK on port: {}".format(self.outbound_port, self.inbound_port))
        while True:
            try:
                self.simulator.u_send(data)  # send data
                ack = self.simulator.u_receive()  # receive ACK
                self.logger.info("Got ACK from socket: {}".format(
                    ack.decode('ascii')))  # note that ASCII will only decode bytes in the range 0-127
                break
            except socket.timeout:
                pass


def int_to_byte(num, length):
    byte_arr = [0] * length
    temp = length - 1
    while num != 0:
        byte_arr[temp] = num % 256
        temp -= 1
        num /= 256
    return byte_arr


def byte_to_int(data, length):
    num = 0
    for i in xrange(length):
        num *= 256
        num += data[i]

    return num


class victorbigbrain(BogoSender):
    def __init__(self, BUFFSIZE):
        super(victorbigbrain, self).__init__()
        self.BUFFSIZE = BUFFSIZE
        self.data = None
        self.PSIZE = BUFFSIZE - 40

    def fletcher32(self, data, length):
        if length == 0:
            length = len(data)
        w_len = length
        c0 = 0
        c1 = 0
        x = 0

        while w_len >= 360:
            for i in range(360):
                c0 = c0 + ord(data[x])
                c1 = c1 + c0
                x = x + 1
            c0 = c0 % 65535
            c1 = c1 % 65535
            w_len = w_len - 360

        for i in range(w_len):
            c0 = c0 + ord(data[x])
            c1 = c1 + c0
            x = x + 1
        c0 = c0 % 65535
        c1 = c1 % 65535
        return (c1 << 16 | c0)

    def send(self, data):
        self.data = copy.copy(data)
        self.logger.info(
            "Sending on port: {} and waiting for ACK on port: {}".format(self.outbound_port, self.inbound_port))
        size = len(data)
        n_iters = size / self.PSIZE
        if (float(size) / self.PSIZE > n_iters):
            n_iters += 1
        self.logger.info("n_iters: {}".format(n_iters))
        # print(n_iters)

        index = [0] * n_iters
        temp = size
        print(temp)
        sending = 1
        while (True):
            temp = size
            for i in xrange(n_iters):
                if (index[i] == 0):
                    self.logger.info("sending: {}".format(i))
                    index[i] = 1
                    tosend = bytearray([0] * (self.BUFFSIZE - 32))
                    tosend[0] = 127
                    # print(ord(bytes(tosend)[0]))

                    # tosend[0:1024]=data[i*self.BUFFSIZE:i*self.BUFFSIZE+min(self.BUFFSIZE,temp)]
                    tosend[1:4] = int_to_byte(i, 3)
                    tosend[4:8] = int_to_byte(temp, 4)
                    tosend[8:8 + min(self.PSIZE, temp)] = data[i * self.PSIZE:i * self.PSIZE + min(self.PSIZE, temp)]
                    checksum = self.fletcher32(bytes(tosend), len(tosend))
                    # self.logger.info(checksum)
                    tosend = tosend + bytearray(int_to_byte(checksum, 32))
                    # self.logger.info(sys.getsizeof(bytes(tosend)))
                    self.simulator.u_send(tosend)
                temp -= self.PSIZE
            tosend2 = bytearray([0] * (self.BUFFSIZE - 32))
            tosend2[0] = 0
            tosend2[4:8] = int_to_byte(size, 4)
            checksum = self.fletcher32(bytes(tosend2), len(tosend2))
            self.logger.info(checksum)
            tosend2 = tosend2 + bytearray(int_to_byte(checksum, 32))
            self.simulator.u_send(tosend2)
            self.logger.info("Done")
            feedback = self.simulator.u_receive()
            self.logger.info(feedback)
            intarr=[]
            getint=0
            for i in feedback:
                k=i-ord('0')
                if(k<=9 and k>=0):
                    getint*=10
                    getint+=k
                elif(i==ord(',') or i==ord(']')):
                    intarr=intarr+[getint]
                    getint=0
            sum=0
            for i in xrange(100):
                sum+=intarr[i]
            if(sum==intarr[100]):
                self.logger.info("successful")
                if(intarr[0]>2*size):
                    sys.exit()
                for i in xrange(100):
                    if(intarr[i]>0):
                        index[intarr[i]-1]=0 #index updated for next send




if __name__ == "__main__":
    # test out BogoSender
    DATA = bytes(sys.stdin.read())

    sndr = victorbigbrain(900)
    sndr.send(DATA)
