from pipeline_simulator.core import instructions, memories
import logging


logger = logging.getLogger(__name__)


class DependencyAnalyzer:

    _tmp = []
    _count = 0
    _raw = []
    _waw = []
    _war = []

    def add_instruction(self, inst: instructions.Instruction):
        self._tmp.append(inst)

    def analyze(self):
        for i, instruction1 in enumerate(self._tmp):
            for j, instruction2 in enumerate(self._tmp[i+1:]):
                # RAW
                for inst1_register in instruction1.get_written_registers():
                    for inst2_register in instruction2.get_read_registers():
                        if inst1_register == inst2_register:
                            self._raw.append((instruction1, instruction2, inst1_register))

                # WAW
                for inst1_register in instruction1.get_written_registers():
                    for inst2_register in instruction2.get_written_registers():
                        if inst1_register == inst2_register:
                            self._waw.append((instruction1, instruction2, inst1_register))

                # WAR
                for inst1_register in instruction1.get_read_registers():
                    for inst2_register in instruction2.get_written_registers():
                        if inst1_register == inst2_register:
                            self._war.append((instruction1, instruction2, inst1_register))

    def print(self):
        print("-----------------")
        print("Dependencyas RAW")
        print("-----------------")
        for dependency in self._raw:
            print("%s -> %s [por %s]" % dependency)

        print("-----------------")
        print("Dependencias WAW")
        print("-----------------")
        for dependency in self._waw:
            print("%s -> %s [por %s]" % dependency)

        print("-----------------")
        print("Dependencias WAR")
        print("-----------------")
        for dependency in self._war:
            print("%s -> %s [por %s]" % dependency)


class Parser:

    _instruction_regex = r"^((?P<label>\w*):\s)?(?P<opcode>\w*)\s*(?P<op1>[a-zA-Z0-9|(|)]*)?(,\s" \
            r"*(?P<op2>[a-zA-Z0-9|(|)]*))?(,\s*(?P<op3>\w*))?([\s|\t]*#.*)?$"

    _dependency_analyzer = DependencyAnalyzer()

    def __init__(self, registers: memories.RegisterSet, memory: memories.Memory, print_dependencies=False):
        self._registers = registers
        self._memory = memory
        self._print_dependencies = print_dependencies

    def parse_register(self, alias):
        return self.__get_register(alias)

    def parse(self, filepath: str):
        logger.info("Parsing file '%s'." % filepath)
        program = []

        # Analyze labels
        labels = {}
        nline = 0
        with open(filepath, 'r') as f:
            for line in f:
                if line.startswith('#'):  # Skip comments
                    continue

                label = self.__check_label(line, nline)
                if label:
                    labels[label] = nline
                nline += 1

        # Load program
        nline = 0
        with open(filepath, 'r') as f:
            for line in f:
                if line.startswith('#'):  # Skip comments
                    continue

                instruction = self.__parse_line(line, nline, labels)
                self._dependency_analyzer.add_instruction(instruction)
                program.append(instruction)
                nline += 1

        logger.info("Parsed %d instructions successfully." % nline)

        self._dependency_analyzer.analyze()
        if self._print_dependencies:
            self._dependency_analyzer.print()

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
            if opcode in instructions.AluInstruction.opcodes:
                if not (op1 and op2 and op3):
                    raise NotEnoughOperandsError(nline)

                instruction = instructions.AluInstruction(
                    opcode=opcode,
                    rd=self.__get_register(op1),
                    rs=self.__get_register(op2),
                    rt=self.__get_register(op3))

            elif opcode in instructions.MemInstruction.opcodes:
                if not (op1 and op2):
                    raise NotEnoughOperandsError(nline)

                offset = self.__get_offset(op2)

                if opcode == 'LOAD':
                    instruction = instructions.MemInstruction(
                        opcode=opcode,
                        rd=self.__get_register(op1),
                        rs=self.__get_register(op2),
                        offset=offset,
                        memory=self._memory)
                else:  # opcode == 'STORE'
                    instruction = instructions.MemInstruction(
                        opcode=opcode,
                        rd=self.__get_register(op2),
                        rs=self.__get_register(op1),
                        offset=offset,
                        memory=self._memory)

            elif opcode in instructions.BranchInstruction.opcodes:
                if not (op1 and op2 and op3):
                    raise NotEnoughOperandsError(nline)

                instruction = instructions.BranchInstruction(
                    opcode=opcode,
                    rs=self.__get_register(op1),
                    rt=self.__get_register(op2),
                    imm=self.__label2addr(labels, op3))

            elif opcode in instructions.JumpInstruction.opcodes:
                if not op1:
                    raise NotEnoughOperandsError(nline)

                instruction = instructions.JumpInstruction(
                    opcode=opcode,
                    imm=self.__label2addr(labels, op1)
                )
            elif opcode in instructions.HaltInstruction.opcodes:
                instruction = instructions.HaltInstruction(opcode)

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
