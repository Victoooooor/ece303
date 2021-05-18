# Written by S. Mevawala, modified by D. Gitzel

import logging

import channelsimulator
import utils
import sys
import socket

class Receiver(object):

    def __init__(self, inbound_port=50005, outbound_port=50006, timeout=0.05, debug_level=logging.INFO):
        self.logger = utils.Logger(self.__class__.__name__, debug_level)

        self.inbound_port = inbound_port
        self.outbound_port = outbound_port
        self.simulator = channelsimulator.ChannelSimulator(inbound_port=inbound_port, outbound_port=outbound_port,
                                                           debug_level=debug_level)
        self.simulator.rcvr_setup(timeout)
        self.simulator.sndr_setup(timeout)

    def receive(self):
        raise NotImplementedError("The base API class has no implementation. Please override and add your own.")


class BogoReceiver(Receiver):
    ACK_DATA = bytes(123)

    def __init__(self):
        super(BogoReceiver, self).__init__()

    def receive(self):
        self.logger.info("Receiving on port: {} and replying with ACK on port: {}".format(self.inbound_port, self.outbound_port))
        while True:
            try:
                data = self.simulator.u_receive()  # receive data
                self.logger.info("Got data from socket: {}".format(data.decode('ascii')))  # note that ASCII will only decode bytes in the range 0-127
                # sys.stdout.write(data)
                # self.simulator.u_send(BogoReceiver.ACK_DATA)  # send ACK
            except socket.timeout:
                sys.exit()

def int_to_byte(num,length):
    byte_arr=[0]*length
    temp=length-1
    while num!=0:
        byte_arr[temp]=num%256
        temp-=1
        num/=256
    return byte_arr

def byte_to_int(data,length):
    num=0
    for i in xrange(length):
        num *= 256
        num+=data[i]

    return num

class victorsmollbrain(BogoReceiver):
    def __init__(self,BUFFSIZE):
        super(victorsmollbrain,self).__init__()
        self.BUFFSIZE = BUFFSIZE
        self.data = None
        self.PSIZE = BUFFSIZE - 40

    def fletcher32(self,data, length):
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

    def receive(self):
        self.logger.info(
            "Receiving on port: {} and replying with ACK on port: {}".format(self.inbound_port, self.outbound_port))
        size=0
        n_iters=1
        index=[0]
        stored=None
        count=None
        while (True):
            try:
                data = self.simulator.u_receive()
                if (len(data)!=self.BUFFSIZE):
                    continue
                pivot=self.BUFFSIZE-32
                checksum_sent=byte_to_int(data[self.BUFFSIZE-4:],4)
                checksum_calc=self.fletcher32(bytes(data[0:pivot]),pivot)
                if(checksum_sent!=checksum_calc):
                    continue
                self.logger.info("no error")
                i=byte_to_int(data[1:4],3)
                temp=byte_to_int(data[4:8],4)
                type=data[0]
                if (size==0):#this is first successfully received packet
                    if(type==127):
                        size+=i*self.PSIZE
                    size+=temp
                    n_iters = size / self.PSIZE
                    if (float(size) / self.PSIZE > n_iters):
                        n_iters += 1
                    count=n_iters
                    index = [0] * n_iters
                    stored = bytearray(size)
                if(type==127):
                    count-=1
                    index[i]=1
                    stored[i*self.PSIZE:i*self.PSIZE+min(self.PSIZE,temp)]=data[8:8+min(self.PSIZE,temp)]
                    self.logger.info("writing left: {}".format(count))
                elif(type==0):
                    self.logger.info("sending lost")
                    tosend = [0] * 100
                    losscount=0
                    for i in xrange(n_iters):
                        if(index[i]==0):
                            tosend[losscount]=i+1
                            losscount+=1
                        if(losscount==100):
                            break
                    sumed = sum(tosend)
                    tosend = tosend + [sumed]
                    self.simulator.u_send(bytes(tosend))
                if (count==0):
                    self.logger.info("Finished")
                    break
            except socket.timeout:
                sys.exit()
        sys.stdout.write(bytes(stored))
        for i in xrange(10):
            tosend = [0] * 100
            tosend[0]=3*size
            tosend = tosend + [tosend[0]]
            self.simulator.u_send(bytes(tosend))

        # self.logger.info("Disconnecting")
        # #Disconnecting sequence:
        # state=0
        # while(True):
        #     try:
        #         data = self.simulator.u_receive()
        #         if (len(data) == self.BUFFSIZE):
        #             pivot = self.BUFFSIZE - 32
        #             self.logger.info(self.fletcher32(bytes(data[0:pivot]), pivot))
        #             checksum_sent = byte_to_int(data[pivot:], 32)
        #             checksum_calc = self.fletcher32(bytes(data[0:pivot]), pivot)
        #             if (checksum_sent == checksum_calc):
        #                 if(data[0]==255):
        #                     break
        #             else:
        #                 if(state>10):
        #                     break
        #         tosend = bytearray([0] * (self.BUFFSIZE - 32))
        #         tosend[0]=127
        #         checksum = self.fletcher32(bytes(tosend), len(tosend))
        #         tosend = tosend + bytearray(int_to_byte(checksum, 32))
        #         self.simulator.u_send(tosend)
        #         state+=1
        #         self.logger.info(state)
        #     except socket.timeout:
        #         self.logger.info("Time out: Done")
        #         sys.exit()
        # self.logger.info("Done")
        # sys.stderr.write("Done")

if __name__ == "__main__":
    # test out BogoReceiver
    rcvr = victorsmollbrain(900)
    rcvr.receive()
    sys.stdout.flush()