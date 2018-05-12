import logging
from pipeline_simulator.core import memories


logger = logging.getLogger(__name__)


class Instruction:

    def fetch(self):
        logger.info("Executing fetch phase of instruction " + self.__repr__())

    def decode(self):
        logger.info("Executing decode phase of instruction " + self.__repr__())

    def execute(self):
        logger.info("Executing execute phase of instruction " + self.__repr__())

    def memory(self):
        logger.info("Executing memory phase of instruction " + self.__repr__())

    def writeback(self):
        logger.info("Executing writeback phase of instruction " + self.__repr__())

    def get_read_registers(self):
        pass

    def get_written_registers(self):
        pass

    def has_dependencies(self):
        return False
    
    def get_opcode(self):
        return self._opcode


class Bubble(Instruction):
    def __repr__(self):
        return "( )"


class AluInstruction(Instruction):
    opcodes = [
        'ADD',
        'MULT',
        'SUB',
        'DIV',
    ]

    fu_cycles = {
        'ADD': 1,
        'MULT': 1,
        'SUB': 1,
        'DIV': 1
    }

    def __init__(self, opcode, rs: memories.Register, rt: memories.Register, rd: memories.Register):
        self._opcode = opcode
        self._rs = rs
        self._rt = rt
        self._rd = rd
        self._tmp = None  # Used for store results before writing them to rd on WB phase
        self._remaining_cycles = self.fu_cycles[self._opcode] - 1

    def decode(self):
        super(AluInstruction, self).decode()
        if self._rs.is_locked() or self._rt.is_locked():
            raise RawDependencySignal
        self._rd.lock()

    def execute(self):
        if self._remaining_cycles > 0:
            self._remaining_cycles -= 1
            raise FunctionalUnitNotFinishedSignal

        super(AluInstruction, self).execute()
        if self._opcode == 'ADD':
            self._tmp = self._rs.get_data() + self._rt.get_data()
        elif self._opcode == 'MULT':
            self._tmp = self._rs.get_data() * self._rt.get_data()
        elif self._opcode == 'SUB':
            self._tmp = self._rs.get_data() - self._rt.get_data()
        elif self._opcode == 'DIV':
            self._tmp = self._rs.get_data() / self._rt.get_data()
            self._tmp = int(self._tmp)  # integer division

    def writeback(self):
        super(AluInstruction, self).writeback()
        self._rd.unlock()
        self._rd.set(self._tmp)

    def get_read_registers(self):
        return [self._rs, self._rt]

    def get_written_registers(self):
        return [self._rd]

    def __repr__(self):
        return "%s %s, %s, %s" % (self._opcode, self._rd, self._rs, self._rt)


class MemInstruction(Instruction):
    opcodes = [
        'LOAD',
        'STORE',
    ]

    fu_cycles = {
        'LOAD': 1,
        'STORE': 1,
    }

    def __init__(self, opcode, rs: memories.Register, rd: memories.Register, offset: int, memory: memories.Memory):
        self._opcode = opcode
        self._rs = rs
        self._rd = rd
        self._offset = offset
        self._computed_mem_addr = None
        self._tmp = None
        self._memory = memory
        self._remaining_cycles = MemInstruction.fu_cycles[self._opcode] - 1

    def decode(self):
        super(MemInstruction, self).decode()
        if self._opcode == 'LOAD':
            if self._rs.is_locked():
                raise RawDependencySignal
            self._rd.lock()

        else:  # self._opcode == STORE
            if self._rs.is_locked() or self._rd.is_locked():
                raise RawDependencySignal

    def execute(self):
        if self._remaining_cycles > 0:
            self._remaining_cycles -= 1
            raise FunctionalUnitNotFinishedSignal

        super(MemInstruction, self).execute()
        if self._opcode == 'LOAD':
            self._computed_mem_addr = self._rs.get_data() + self._offset

        else:  # self._opcode == STORE
            self._computed_mem_addr = self._rd.get_data() + self._offset

    def memory(self):
        super(MemInstruction, self).memory()
        if self._opcode == 'LOAD':
            self._tmp = self._memory.get_data(self._computed_mem_addr)

        else:  # self._opcode == STORE
            register_data = self._rs.get_data()
            self._memory.set(self._computed_mem_addr, register_data)

    def writeback(self):
        super(MemInstruction, self).writeback()
        if self._opcode == 'LOAD':
            self._rd.unlock()
            self._rd.set(self._tmp)

        else:
            pass

    def get_read_registers(self):
        if self._opcode == 'LOAD':
            return [self._rs]

        elif self._opcode == 'STORE':
            return [self._rs, self._rd]

        else:
            raise RuntimeError

    def get_written_registers(self):
        if self._opcode == 'LOAD':
            return [self._rd]

        elif self._opcode == 'STORE':
            return []

        else:
            raise RuntimeError

    def __repr__(self):
        return "%s %s, %d(%s)" % (self._opcode, self._rd, self._offset, self._rs)


class BranchInstruction(Instruction):
    opcodes = [
        'BEQ',
        'BNE'
    ]

    def __init__(self, opcode, rs: memories.Register, rt: memories.Register, imm: int):
        self._opcode = opcode
        self._rs = rs
        self._rt = rt
        self._imm = imm

    def decode(self):
        if self._rs.is_locked() or self._rt.is_locked():
            raise RawDependencySignal

        if self._opcode == 'BEQ':
            if self._rs.get_data() == self._rt.get_data():
                raise JumpSignal(self._imm)

        elif self._opcode == 'BNE':
            if self._rs.get_data() != self._rt.get_data():
                raise JumpSignal(self._imm)

    def get_read_registers(self):
        return [self._rs, self._rt]

    def get_written_registers(self):
        return []

    def __repr__(self):
        return "%s %s, %s, 0x%x" % (self._opcode, self._rs, self._rt, self._imm)


class JumpInstruction(Instruction):
    opcodes = [
        'JMP',
    ]

    def __init__(self, opcode, imm: int):
        self._opcode = opcode
        self._imm = imm

    def decode(self):
        raise JumpSignal(self._imm)

    def get_read_registers(self):
        return []

    def get_written_registers(self):
        return []

    def __repr__(self):
        return "%s 0x%x" % (self._opcode, self._imm)


class HaltInstruction(Instruction):
    opcodes = [
        'HALT',
    ]

    def __init__(self, opcode):
        self._opcode = opcode

    def __repr__(self):
        return "%s" % self._opcode

    def decode(self):
        raise HaltSignal

    def get_read_registers(self):
        return []

    def get_written_registers(self):
        return []


class HaltSignal(Exception):
    pass


class RawDependencySignal(Exception):
    pass


class JumpSignal(Exception):
    def __init__(self, addr):
        self.addr = addr


class FunctionalUnitNotFinishedSignal(Exception):
    pass
