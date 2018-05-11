import logging
import collections
from .instructions import Instruction, HaltInstruction, Bubble, \
    HaltSignal, RawDependencySignal, JumpSignal, FunctionalUnitNotFinishedSignal
from .memories import Memory, RegisterSet


logger = logging.getLogger(__name__)

_statistics = {
    'cycles': 0,
    'instructions': 0,
}


class Cpu:

    def __init__(self, registers: RegisterSet, memory: Memory, scalability=1, phase_cycles=(1, 1, 1, 1, 1), show_chronogram=False):
        self._PHASE_CYCLES = phase_cycles
        self._status = self.CpuStatus.HALTED
        self._registers = registers
        self._memory = memory
        self._pc = 0
        self._scalability = scalability
        self._show_chronogram = show_chronogram

    class CpuStatus:
        RUNNING = 0
        STOPPING = 1
        HALTED = 2

    def start(self):
        self.set_running()

    def step(self):
        pass

    def is_halted(self):
        return self._status == self.CpuStatus.HALTED

    def is_running(self):
        return self._status == self.CpuStatus.RUNNING

    def is_stopping(self):
        return self._status == self.CpuStatus.STOPPING

    def set_halted(self):
        logger.info("CPU status is now HALTED.")
        self._status = self.CpuStatus.HALTED

    def set_stopping(self):
        logger.info("CPU status is now STOPPING.")
        self._status = self.CpuStatus.STOPPING

    def set_running(self):
        logger.info("CPU status is now RUNNING.")
        self._status = self.CpuStatus.RUNNING


class Chronogram:

    def __init__(self):
        self._current_cycle = 0
        self._chronogram = collections.OrderedDict()
        self._instruction_map = {}

    def increase_cycle(self):
        self._current_cycle += 1

    def set_instruction_stage(self, instruction_id, instruction_str, stage):
        self.__add_instruction(instruction_id, instruction_str)
        self._chronogram[instruction_id][self._current_cycle] = stage

    def __add_instruction(self, instruction_id, instruction_str):
        if instruction_id not in self._chronogram:
            self._chronogram[instruction_id] = collections.OrderedDict()
            self._instruction_map[instruction_id] = instruction_str

    def print(self):
        # Header
        print("\t\t\t\t\t|\t", end='')
        for i in range(1, _statistics['cycles']+1):
            print(str(i) + "\t", end='')
        print("")

        # Instructions chronogram
        for instruction_id, cycles in self._chronogram.items():
            instruction_str = self._instruction_map[instruction_id]

            if len(instruction_str) < 4:
                print(instruction_str + "\t\t\t\t\t|\t", end='')
            elif len(instruction_str) < 8:
                print(instruction_str + "\t\t\t\t|\t", end='')
            elif len(instruction_str) < 12:
                print(instruction_str + "\t\t\t|\t", end='')
            elif len(instruction_str) < 16:
                print(instruction_str + "\t\t|\t", end='')
            else:
                print(instruction_str + "\t|\t", end='')

            left_padding = (list(cycles.keys()))[0]
            for tab in range(left_padding):
                print('\t', end='')

            for cycle, stage in cycles.items():
                print(Pipeline.PipelineStage.to_str(stage) + '\t', end='')

            print("")


class Pipeline:

    _id_counter = 0

    class PipelineStage:
        IF = 1
        ID = 2
        EX = 3
        MEM = 4
        WB = 5

        @classmethod
        def to_str(cls, stage):
            if stage == cls.IF:
                return 'F'
            elif stage == cls.ID:
                return 'D'
            elif stage == cls.EX:
                return 'X'
            elif stage == cls.MEM:
                return 'M'
            elif stage == cls.WB:
                return 'W'
            else:
                " Programming error "
                raise RuntimeError

    def __init__(self, phase_cycles, pipeline_chronogram):
        self._pipeline = {
            self.PipelineStage.IF: Bubble(),
            self.PipelineStage.ID: Bubble(),
            self.PipelineStage.EX: Bubble(),
            self.PipelineStage.MEM: Bubble(),
            self.PipelineStage.WB: Bubble(),
        }
        self._pipeline_ids = {
            self.PipelineStage.IF: -5,
            self.PipelineStage.ID: -4,
            self.PipelineStage.EX: -3,
            self.PipelineStage.MEM: -2,
            self.PipelineStage.WB: -1,
        }
        self._phase_cycles = phase_cycles
        self._remaining_cycles = {
            self.PipelineStage.IF: phase_cycles[0],
            self.PipelineStage.ID: phase_cycles[1],
            self.PipelineStage.EX: phase_cycles[2],
            self.PipelineStage.MEM: phase_cycles[3],
            self.PipelineStage.WB: phase_cycles[4],
        }
        self._pipeline_chronogram = pipeline_chronogram

    def fetch(self, next_instruction: Instruction):
        self.__move(self.PipelineStage.IF, self.PipelineStage.ID)
        logger.info("Loading into IF stage instruction '%s'." % next_instruction)
        self.__set(self.PipelineStage.IF, next_instruction)
        self._pipeline_ids[self.PipelineStage.IF] = self._id_counter
        Pipeline._id_counter += 1

    def decode(self):
        """
        It is possible that decode() throws a HaltSignal, the instruction will be moved from ID to EX anyway
        """
        instruction = self.__get(self.PipelineStage.ID)

        # Only count cycles if is not a Bubble
        if not isinstance(instruction, Bubble):
            if self.__get_remaining_cycles(self.PipelineStage.ID) > 1:
                self.__decrease_remaining_cycles(self.PipelineStage.ID)
                raise StageNotFinishedSignal
            else:
                self.__reset_remaining_cycles(self.PipelineStage.ID)

        try:
            signal = None
            instruction.decode()

        except HaltSignal as s:
            signal = s

        except JumpSignal as s:
            signal = s

        self.__move(self.PipelineStage.ID, self.PipelineStage.EX)

        if signal:
            raise signal

    def execute(self):
        instruction = self.__get(self.PipelineStage.EX)

        # Only count cycles if is not a Bubble
        if not isinstance(instruction, Bubble):
            if self.__get_remaining_cycles(self.PipelineStage.EX) > 1:
                self.__decrease_remaining_cycles(self.PipelineStage.EX)
                raise StageNotFinishedSignal
            else:
                self.__reset_remaining_cycles(self.PipelineStage.EX)

        instruction.execute()
        self.__move(self.PipelineStage.EX, self.PipelineStage.MEM)

    def memory(self):
        instruction = self.__get(self.PipelineStage.MEM)

        # Only count cycles if is not a Bubble
        if not isinstance(instruction, Bubble):
            if self.__get_remaining_cycles(self.PipelineStage.MEM) > 1:
                self.__decrease_remaining_cycles(self.PipelineStage.MEM)
                raise StageNotFinishedSignal
            else:
                self.__reset_remaining_cycles(self.PipelineStage.MEM)

        instruction.memory()
        self.__move(self.PipelineStage.MEM, self.PipelineStage.WB)

    def writeback(self):
        instruction = self.__get(self.PipelineStage.WB)
        instruction.writeback()

        # Only count cycles if is not a Bubble
        if not isinstance(instruction, Bubble):
            if self.__get_remaining_cycles(self.PipelineStage.WB) > 1:
                self.__decrease_remaining_cycles(self.PipelineStage.WB)
                raise StageNotFinishedSignal
            else:
                self.__reset_remaining_cycles(self.PipelineStage.WB)

        if not isinstance(instruction, Bubble):
            _statistics['instructions'] += 1

    def is_empty(self):
        """ A pipe is empty if after the HALT instruction there's only BUBBLEs """
        halt_instruction_found = False
        no_more_instructions = True

        for stage, instruction in self._pipeline.items():
            if halt_instruction_found:
                if not isinstance(instruction, Bubble):  # Normal instruction detected after HALT
                    no_more_instructions = False

            if isinstance(instruction, HaltInstruction):
                halt_instruction_found = True

        return halt_instruction_found and no_more_instructions

    def flush(self):
        """
        Replaces the instruction in the IF stage with a Bubble
        """
        self.__set(self.PipelineStage.IF, Bubble())

    def stall(self, stage):
        """
        Instead of moving the instruction of the current stage to the next one,
        a bubble is inserted in the next stage and the instructions
        of the previous stages are neither moved nor executed.
        """
        if stage != self.PipelineStage.WB:
            self.__set(stage + 1, Bubble())

    def increase_cycle(self):
        self._pipeline_chronogram.increase_cycle()

    def update_chronogram(self):
        for stage in self._pipeline.keys():
            instruction = self._pipeline[stage]
            instruction_id = self._pipeline_ids[stage]

            if isinstance(instruction, Instruction) and not isinstance(instruction, Bubble):
                self._pipeline_chronogram.set_instruction_stage(instruction_id, instruction.__str__(), stage)


    def __move(self, stage_src, stage_dst):
        logger.info("Moving from stage %s to stage %s instruction '%s' ."
                    % (stage_src, stage_dst, self._pipeline[stage_src]))

        self._pipeline[stage_dst] = self._pipeline[stage_src]
        self._pipeline_ids[stage_dst] = self._pipeline_ids[stage_src]

    def __get(self, stage):
        return self._pipeline[stage]

    def __set(self, stage, instruction: Instruction):
        self._pipeline[stage] = instruction

    def __get_remaining_cycles(self, stage):
        return self._remaining_cycles[stage]

    def __decrease_remaining_cycles(self, stage):
        self._remaining_cycles[stage] -= 1

    def __reset_remaining_cycles(self, stage):
        self._remaining_cycles[stage] = self._phase_cycles[stage-1]  # Phase ID - 1 = phase cycles list's index

    def __repr__(self):
        return ("\n1. %s \t[%d]\n2. %s \t[%d]\n3. %s \t[%d]\n4. %s \t[%d]\n5. %s \t[%d]" %
                (self.__get(self.PipelineStage.IF), self._pipeline_ids[self.PipelineStage.IF],
                 self.__get(self.PipelineStage.ID), self._pipeline_ids[self.PipelineStage.ID],
                 self.__get(self.PipelineStage.EX), self._pipeline_ids[self.PipelineStage.EX],
                 self.__get(self.PipelineStage.MEM), self._pipeline_ids[self.PipelineStage.MEM],
                 self.__get(self.PipelineStage.WB), self._pipeline_ids[self.PipelineStage.WB],))


class PipelinedCpu(Cpu):

    def __init__(self, *args, **kwargs):
        super(PipelinedCpu, self).__init__(*args, **kwargs)
        self._pipeline_chronogram = Chronogram()
        self._pipeline = Pipeline(self._PHASE_CYCLES, self._pipeline_chronogram)

    def step(self):
        if self.is_halted():
            raise HaltedCpuError

        logger.info("Processing cycle %d." % _statistics['cycles'])
        current_stage = None

        try:
            current_stage = Pipeline.PipelineStage.WB
            self._pipeline.writeback()

            current_stage = Pipeline.PipelineStage.MEM
            self._pipeline.memory()

            current_stage = Pipeline.PipelineStage.EX
            self._pipeline.execute()

            current_stage = Pipeline.PipelineStage.ID
            self._pipeline.decode()

            if self.is_running():
                " If RUNNING, the next instruction is got from the memory "
                next_instruction = self._memory.get_data(self._pc)
                self._pc += 1
            elif self.is_stopping():
                " If STOPPING, the next instruction is a Bubble "
                next_instruction = Bubble()
            else:
                " Programming error "
                raise RuntimeError

            current_stage = Pipeline.PipelineStage.IF
            self._pipeline.fetch(next_instruction)

        except HaltSignal:
            logger.info("Halt signal received.")
            if self.is_running():
                self.set_stopping()
                self._pipeline.flush()  # Last fetched instruction is wrong, it must be a BUBBLE

            self._pipeline.fetch(Bubble())

        except RawDependencySignal:
            logger.info("RAW dependency signal received.")
            self._pipeline.stall(current_stage)

        except JumpSignal as s:
            logger.info("Jump signal received.")
            self._pipeline.flush()
            self._pc = s.addr

            if self.is_running():
                " If RUNNING, the next instruction is got from the memory "
                next_instruction = self._memory.get_data(self._pc)
                self._pc += 1
            elif self.is_stopping():
                " If STOPPING, the next instruction is a Bubble "
                next_instruction = Bubble()
            else:
                " Programming error "
                raise RuntimeError

            self._pipeline.fetch(next_instruction)

        except (StageNotFinishedSignal, FunctionalUnitNotFinishedSignal):
            self._pipeline.stall(current_stage)

        finally:
            logger.info(self._pipeline)
            logger.info("Cycle done.\n\n")

            self._pipeline.update_chronogram()
            self._pipeline_chronogram.increase_cycle()

            if self.is_stopping() and self._pipeline.is_empty():
                if self._show_chronogram:
                    self._pipeline_chronogram.print()
                self.set_halted()

            _statistics['cycles'] += 1


class ExecutionUnit:

    _latency = 1

    def __init__(self, id, chronogram):
        self._id = id
        self._instruction = None
        self._instruction_id = None
        self._execution_finished = False
        self._chronogram = chronogram
        self._remaining_cycles = self.__class__._latency - 1

    def add(self, instruction: Instruction, instruction_id: int):
        self._instruction = instruction
        self._instruction_id = instruction_id

    def execute(self):
        logger.info("Executing unit #%d" % self._id)
        if not self._instruction:
            logger.info("Execution unit #%d has no instruction to execute" % self._id)
            return

        if self._execution_finished:
            logger.info("Processing writeback of instruction %s" % self._instruction)
            self._chronogram.set_instruction_stage(self._instruction_id, self._instruction.__str__(), Pipeline.PipelineStage.WB)
            self._instruction.writeback()
            self._instruction = None
            self._instruction_id = None
            self.__reset_remaining_cycles()
            self._execution_finished = False

        else:
            self._chronogram.set_instruction_stage(self._instruction_id, self._instruction.__str__(), Pipeline.PipelineStage.EX)
            logger.info("Cycles remaining to execute: %d" % self._remaining_cycles)

            if self._remaining_cycles > 0:
                self._remaining_cycles -= 1
                return

            try:
                logger.info("Decoding and executing instruction %s" % self._instruction)
                self._instruction.decode()
                self._instruction.execute()
                self._instruction.memory()
                self._execution_finished = True

            except RawDependencySignal:
                logger.info("Received RawDependencySignal signal")
                return

            except FunctionalUnitNotFinishedSignal:
                logger.info("Received FunctionalUnitNotFinishedSignal signal")
                return

    def allows(self, instruction: Instruction):
        return instruction.get_opcode() == 'HALT'

    def is_free(self):
        return self._instruction is None

    def has_halt(self):
        return isinstance(self._instruction, HaltInstruction)

    def get_id(self):
        return self._id

    def get_instruction_id(self):
        if self._instruction_id:
            return self._instruction_id
        else:
            return -1

    def __reset_remaining_cycles(self):
        self._remaining_cycles = self.__class__._latency - 1

    def __repr__(self):
        return "#%d [%s]: Instruction: %s" % (self._id, self.__class__, self._instruction)


class AddExecutionUnit(ExecutionUnit):

    _latency = 1

    def allows(self, instruction: Instruction):
        return super(AddExecutionUnit, self).allows(instruction) or \
               instruction.get_opcode() == 'ADD' or \
               instruction.get_opcode() == 'SUB'


class MultExecutionUnit(ExecutionUnit):

    _latency = 1

    def allows(self, instruction: Instruction):
        return super(MultExecutionUnit, self).allows(instruction) or \
               instruction.get_opcode() == 'MULT' or \
               instruction.get_opcode() == 'DIV'


class MemoryExecutionUnit(ExecutionUnit):

    _latency = 1

    def allows(self, instruction: Instruction):
        return super(MemoryExecutionUnit, self).allows(instruction) or \
               instruction.get_opcode() == 'LOAD' or \
               instruction.get_opcode() == 'STORE'


class ShelvingBuffer:
    _id_counter = 0

    def __init__(self, execution_units):
        self._buffer = []
        self._buffer_ids = []
        self._execution_units = execution_units

    def add(self, instruction: Instruction):
        instruction_id = ShelvingBuffer._id_counter
        ShelvingBuffer._id_counter += 1

        self._buffer.append(instruction)
        self._buffer_ids.append(instruction_id)

        logger.info("Loading new instruction. Shelving buffer content:\n" + "\n".join(map(str, self._buffer)))

        return instruction_id

    def dispatch_next_instruction_to_eu(self):
        if len(self._buffer) == 0:
            logger.info("Shelving buffer empty. No instruction loaded into execution unit.")
            return

        next_instruction = self._buffer[0]
        next_instruction_id = self._buffer_ids[0]

        for execution_unit in self._execution_units:
            if execution_unit.is_free() and execution_unit.allows(next_instruction):
                del self._buffer[0]
                del self._buffer_ids[0]

                logger.info("Loading instruction %s into execution unit #%d" %
                            (next_instruction, execution_unit.get_id()))
                execution_unit.add(next_instruction, next_instruction_id)
                break
        else:
            logger.info("All execution units are busy. No instruction caught from shelving buffer.")

    def is_empty(self):
        return len(self._buffer) == 0


class ReservationStationsCpu(Cpu):

    def __init__(self, *args, **kwargs):
        super(ReservationStationsCpu, self).__init__(*args, **kwargs)


class CentralizedRSCpu(ReservationStationsCpu):

    def __init__(self, *args, **kwargs):
        super(CentralizedRSCpu, self).__init__(*args, **kwargs)
        self._chronogram = Chronogram()
        self._execution_units = [
            AddExecutionUnit(0, self._chronogram),
            MultExecutionUnit(1, self._chronogram),
            MultExecutionUnit(2, self._chronogram),
            MemoryExecutionUnit(3, self._chronogram),
        ]
        self._shelving_buffer = ShelvingBuffer(self._execution_units)

    def step(self):
        if self.is_halted():
            raise HaltedCpuError

        try:
            logger.info("Processing cycle %d." % _statistics['cycles'])

            self.__issue()
            self.__execute()

        except HaltSignal:
            logger.info("Halt signal received.")
            if self.is_running():
                self.set_stopping()

        finally:
            logger.info("Cycle done.\n\n")

            self._chronogram.increase_cycle()
            _statistics['cycles'] += 1

            if self.is_stopping() and self._shelving_buffer.is_empty() and self.__all_eu_empty():
                if self._show_chronogram:
                    self._chronogram.print()
                self.set_halted()

    def __issue(self):
        for _ in range(0, self._scalability):
            if self.is_running():
                " If RUNNING, the next instruction is got from the memory "
                next_instruction = self._memory.get_data(self._pc)

                if not isinstance(next_instruction, Instruction):
                    break  # Ugly fix

                self._pc += 1
                instruction_id = self._shelving_buffer.add(next_instruction)
                self._chronogram.set_instruction_stage(instruction_id, next_instruction.__str__(), Pipeline.PipelineStage.IF)

        self._shelving_buffer.dispatch_next_instruction_to_eu()

    def __execute(self):
        logger.info("Execution units status:\n" + "\n".join(map(str, self._execution_units)))
        for execution_unit in sorted(self._execution_units, key=lambda x: x.get_instruction_id()):
            execution_unit.execute()

    def __all_eu_empty(self):
        all_eu_empty = True
        for eu in self._execution_units:
            if eu.has_halt():
                continue
            elif not eu.is_free():  # todo
                all_eu_empty = False

        return all_eu_empty


class DecentralizedByInstructionsRSCpu(ReservationStationsCpu):

    def __init__(self, *args, **kwargs):
        super(DecentralizedByInstructionsRSCpu, self).__init__(*args, **kwargs)
        self._shelving_buffers = []
        self._execution_units = []


class HaltedCpuError(Exception):
    pass


class StageNotFinishedSignal(Exception):
    pass
