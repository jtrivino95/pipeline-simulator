import logging


logger = logging.getLogger(__name__)


class Register(object):

    def __init__(self, reg_id: int):
        self._register_id = reg_id
        self._data = 0
        self._semaphore = 0

    def set(self, data):
        logger.debug("Storing element in register %d." % self._register_id)
        self._data = data

    def get(self):
        logger.debug("Returning element from register %d." % self._register_id)
        if self.is_locked():
            raise ReadLockedRegisterError(self._register_id)
        return self._data

    def lock(self):
        logger.info("Locking register %d." % self._register_id)
        self._semaphore += 1

    def unlock(self):
        logger.info("Unlocking register %d." % self._register_id)
        if self._semaphore > 0:
            self._semaphore -= 1

    def is_locked(self):
        return self._semaphore > 0

    def __repr__(self):
        # return "R%d[%d][Locked: %s]" % (self._register_id, self._data, self.is_locked())
        return "R%d" % self._register_id


class RegisterSet(object):
    _registers = []

    def __init__(self):
        for i in range(32):
            self._registers.append(Register(i))

    def get(self, register_id):
        try:
            return self._registers[register_id]
        except IndexError:
            raise InvalidRegisterError(register_id)


class Memory:

    def __init__(self, size_in_words):
        self._memory = []
        self._size_in_words = size_in_words
        for i in range(size_in_words):
            self._memory.append(0)

    def get(self, addr):
        logger.debug("Returning from memory element in %d." % addr)
        try:
            return self._memory[addr]
        except IndexError:
            raise InvalidAddressError(addr)

    def set(self, addr, element):
        logger.debug("Storing in memory element in %d." % addr)
        try:
            self._memory[addr] = element
        except IndexError:
            raise InvalidAddressError(addr)

    def load_program(self, program: list, offset=0):
        logger.info("Loading program in memory from addr %d." % offset)
        for index, instruction in enumerate(program):
            self.set(index + offset, instruction)
        logger.info("Program loaded.")

    def __repr__(self):
        dump = ""
        for i in range(self._size_in_words):
            dump += "0x%x:\t%s\n" % (i, self._memory[i])
        return dump


class InvalidAddressError(Exception):

    def __init__(self, addr):
        self._addr = addr

    def __str__(self):
        return "Address %d does not exist." % self._addr


class RegisterError(Exception):
    def __init__(self, register_id):
        self._register_id = register_id


class InvalidRegisterError(RegisterError):
    def __str__(self):
        return "Register %d does not exist." % self._register_id


class WriteToLockedRegisterError(RegisterError):
    def __str__(self):
        return "Unable to write a locked register %d." % self._register_id


class ReadLockedRegisterError(RegisterError):
    def __str__(self):
        return "Unable to read a locked register %d." % self._register_id
