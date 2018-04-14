import logging


logger = logging.getLogger(__name__)


class Register(object):

    def __init__(self, reg_id: int):
        self._register_id = reg_id
        self._data = 0
        self._semaphore = 0

    def set(self, data):
        logger.info("Storing data %d in register %d." % (data, self._register_id))
        self._data = data

    def get_data(self):
        logger.debug("Returning element from register %d." % self._register_id)
        return self._data

    def lock(self):
        logger.debug("Locking register %d." % self._register_id)
        self._semaphore += 1

    def unlock(self):
        logger.debug("Unlocking register %d." % self._register_id)
        if self._semaphore > 0:
            self._semaphore -= 1

    def is_locked(self):
        return self._semaphore > 0

    def __str__(self):
        return "R%d" % self._register_id

    def __repr__(self):
        # return "R%d[%d][Locked: %s]" % (self._register_id, self._data, self.is_locked())
        return "R%d" % (self._register_id)


class RegisterSet(object):
    _registers = []

    def __init__(self, registers_file=None, num_registers=32):
        for i in range(num_registers):
            self._registers.append(Register(i))

        from .compilers import Parser, InstructionSyntaxError
        p = Parser(self, None)
        if registers_file:
            with open(registers_file, 'r') as f:
                for line in f:
                    try:
                        (register_alias, value) = line.split("=")
                        register = p.parse_register(register_alias)
                        register.set(int(value))
                    except ValueError:
                        raise ValueError("Linea mal formada en archivo de registros.")

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

    def get_data(self, addr):
        logger.debug("Returning from memory element in %d." % addr)
        try:
            return self._memory[addr]
        except IndexError:
            raise InvalidAddressError(addr)

    def set(self, addr, data):
        logger.info("Storing in memory data %s in address %d." % (data, addr))
        try:
            self._memory[addr] = data
        except IndexError:
            raise InvalidAddressError(addr)

    def write_program(self, program: list, offset=0):
        logger.info("Writing program in memory from addr %d." % offset)
        for index, instruction in enumerate(program):
            self.set(index + offset, instruction)
        logger.info("Program loaded.")

    def __repr__(self):
        dump = ""
        for i in range(self._size_in_words):
            dump += "%d:\t%s\n" % (i, self._memory[i])
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
