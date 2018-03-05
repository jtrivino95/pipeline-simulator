import logging
from .memories import Register, RegisterSet, Memory


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

    def __init__(self, opcode, rs: Register, rt: Register, rd: Register):
        self._opcode = opcode
        self._rs = rs
        self._rt = rt
        self._rd = rd
        self._tmp = None  # Used for store results before writing them to rd on WB phase

    def decode(self):
        super(AluInstruction, self).decode()
        if self._rs.is_locked() or self._rt.is_locked():
            raise RawDependencySignal()
        self._rd.lock()

    def execute(self):
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

    def __repr__(self):
        return "%s %s, %s, %s" % (self._opcode, self._rd, self._rs, self._rt)


class MemInstruction(Instruction):
    opcodes = [
        'LOAD',
        'STORE',
    ]

    def __init__(self, opcode, rs: Register, rd: Register, offset: int, memory: Memory):
        self._opcode = opcode
        self._rs = rs
        self._rd = rd
        self._offset = offset
        self._computed_mem_addr = None
        self._tmp = None
        self._memory = memory

    def decode(self):
        super(MemInstruction, self).decode()
        if self._opcode == 'LOAD':
            if self._rs.is_locked():
                raise RawDependencySignal()
            self._rd.lock()

        else:  # self._opcode == STORE
            if self._rs.is_locked() or self._rd.is_locked():
                raise RawDependencySignal()

    def execute(self):
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

    def __repr__(self):
        return "%s %s, %s, (offset: %d)" % (self._opcode, self._rd, self._rs, self._offset)


class BranchInstruction(Instruction):
    opcodes = [
        'BEQ',
        'BNE'
    ]

    def __init__(self, opcode, rs: Register, rt: Register, imm: int):
        self._opcode = opcode
        self._rs = rs
        self._rt = rt
        self._imm = imm

    def decode(self):
        if self._rs.is_locked() or self._rt.is_locked():
            raise RawDependencySignal()

        if self._opcode == 'BEQ':
            if self._rs.get_data() == self._rt.get_data():
                raise JumpSignal(self._imm)

        elif self._opcode == 'BNE':
            if self._rs.get_data() != self._rt.get_data():
                raise JumpSignal(self._imm)

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
        raise HaltSignal()


class Parser:
    _instruction_regex = r"^((?P<label>\w*):\s)?(?P<opcode>\w*)\s*(?P<op1>[a-zA-Z0-9|(|)]*)?(,\s" \
            r"*(?P<op2>[a-zA-Z0-9|(|)]*))?(,\s*(?P<op3>\w*))?([\s|\t]*#.*)?$"

    def __init__(self, registers: RegisterSet, memory: Memory):
        self._registers = registers
        self._memory = memory

    def parse(self, filepath: str):
        logger.info("Parsing file '%s'." % filepath)
        program = []

        # Analyze labels
        labels = {}
        nline = 0
        with open(filepath, 'r') as f:
            for line in f:
                label = self.__check_label(line, nline)
                if label:
                    labels[label] = nline
                nline += 1

        # Load program
        nline = 0
        with open(filepath, 'r') as f:
            for line in f:
                instruction = self.__parse_line(line, nline, labels)
                program.append(instruction)
                nline += 1

        logger.info("Parsed %d instructions successfully." % nline)

        return program

    def __parse_line(self, line, nline, labels):
        import re
        match = re.search(self._instruction_regex, line)

        if match:
            instruction_dict = match.groupdict()
        else:
            raise MalformedInstructionError(nline)

        opcode = instruction_dict['opcode']
        op1 = instruction_dict['op1']
        op2 = instruction_dict['op2']
        op3 = instruction_dict['op3']

        try:
            if opcode in AluInstruction.opcodes:
                if not (op1 and op2 and op3):
                    raise NotEnoughOperandsError(nline)

                instruction = AluInstruction(
                    opcode=opcode,
                    rd=self.__get_register(op1),
                    rs=self.__get_register(op2),
                    rt=self.__get_register(op3))

            elif opcode in MemInstruction.opcodes:
                if not (op1 and op2):
                    raise NotEnoughOperandsError(nline)

                offset = self.__get_offset(op2)

                if opcode == 'LOAD':
                    instruction = MemInstruction(
                        opcode=opcode,
                        rd=self.__get_register(op1),
                        rs=self.__get_register(op2),
                        offset=offset,
                        memory=self._memory)
                else:  # opcode == 'STORE'
                    instruction = MemInstruction(
                        opcode=opcode,
                        rd=self.__get_register(op2),
                        rs=self.__get_register(op1),
                        offset=offset,
                        memory=self._memory)

            elif opcode in BranchInstruction.opcodes:
                if not (op1 and op2 and op3):
                    raise NotEnoughOperandsError(nline)

                instruction = BranchInstruction(
                    opcode=opcode,
                    rs=self.__get_register(op1),
                    rt=self.__get_register(op2),
                    imm=self.__label2addr(labels, op3))

            elif opcode in JumpInstruction.opcodes:
                if not op1:
                    raise NotEnoughOperandsError(nline)

                instruction = JumpInstruction(
                    opcode=opcode,
                    imm=self.__label2addr(labels, op1)
                )
            elif opcode in HaltInstruction.opcodes:
                instruction = HaltInstruction(opcode)

            else:
                raise InvalidOpcodeError(opcode=opcode, nline=nline)

        except InvalidOperandError as e:
            raise InvalidOperandError(nline=nline, operand=e.operand)
        except InvalidLabelError as e:
            raise InvalidLabelError(nline=nline, label=e.label)
        except InvalidRegisterError as e:
            raise InvalidRegisterError(nline=nline, register_id=e.register_id)

        return instruction

    def __check_label(self, line, nline):
        import re
        match = re.search(self._instruction_regex, line)

        if match:
            instruction_dict = match.groupdict()
        else:
            raise MalformedInstructionError(nline)

        if 'label' in instruction_dict:
            return instruction_dict['label']
        else:
            return None

    def __get_register(self, alias):
        import re
        regex = r"^((?P<offset>[0-9]+)\()?[r|R](?P<nreg>[0-9]+)\)?$"
        match = re.search(regex, alias)
        if match:
            register_id = int(match.groupdict()['nreg'])
        else:
            raise InvalidOperandError(operand=alias, nline=None)

        try:
            return self._registers.get(register_id)
        except Exception:
            raise InvalidRegisterError(register_id=register_id, nline=None)

    def __get_offset(self, operand):
        import re
        regex = r"^((?P<offset>[0-9]+)\()?[r|R](?P<nreg>[0-9]+)\)?$"
        match = re.search(regex, operand)
        if match:
            return int(match.groupdict()['offset'])
        else:
            raise InvalidOperandError(operand=operand, nline=None)

    def __label2addr(self, labels, label):
        try:
            return labels[label]
        except:
            raise InvalidLabelError(label=label, nline=None)


" Exceptions "


class InstructionSyntaxError(Exception):
    def __init__(self, nline, **kwargs):
        self.nline = nline

    def __str__(self):
        return "Error en linea %d: " % self.nline


class MalformedInstructionError(InstructionSyntaxError):
    def __str__(self):
        return super(MalformedInstructionError, self).__str__() + "instruccion mal construida."


class InvalidOpcodeError(InstructionSyntaxError):
    def __init__(self, opcode, **kwargs):
        self.opcode = opcode
        super(InvalidOpcodeError, self).__init__(**kwargs)

    def __str__(self):
        return super(InvalidOpcodeError, self).__str__() + "opcode '%s' inválido." % self.opcode


class InvalidOperandError(InstructionSyntaxError):
    def __init__(self, operand, **kwargs):
        self.operand = operand
        super(InvalidOperandError, self).__init__(**kwargs)

    def __str__(self):
        return super(InvalidOperandError, self).__str__() + "operando '%s' inválido." % self.operand


class InvalidLabelError(InstructionSyntaxError):
    def __init__(self, label, **kwargs):
        self.label = label
        super(InvalidLabelError, self).__init__(**kwargs)

    def __str__(self):
        return super(InvalidLabelError, self).__str__() + "etiqueta '%s' inválida." % self.label


class InvalidRegisterError(InstructionSyntaxError):
    def __init__(self, register_id, **kwargs):
        self.register_id = register_id
        super(InvalidRegisterError, self).__init__(**kwargs)

    def __str__(self):
        return super(InvalidRegisterError, self).__str__() + "el registro R%s no existe." % self.register_id


class NotEnoughOperandsError(InstructionSyntaxError):
    def __str__(self):
        return super(NotEnoughOperandsError, self).__str__() + "faltan operandos."


class HaltSignal(Exception):
    pass


class RawDependencySignal(Exception):
    pass


class JumpSignal(Exception):
    def __init__(self, addr):
        self.addr = addr