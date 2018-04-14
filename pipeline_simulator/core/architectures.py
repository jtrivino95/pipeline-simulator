import logging
import collections
from .instructions import Instruction, HaltInstruction, Bubble, HaltSignal, RawDependencySignal, JumpSignal
from .memories import Memory, RegisterSet


logger = logging.getLogger(__name__)

_statistics = {
    'cycles': 0,
    'instructions': 0,
}


class Cpu:
    def __init__(self, phase_cycles=[1, 1, 1, 1, 1]):
        self._PHASE_CYCLES = phase_cycles


class PipelinedCpu(Cpu):

    class CpuStatus:
        RUNNING = 0
        STOPPING = 1
        HALTED = 2

    class Pipeline:

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

        class PipelineChronogram:

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
                for i in range(1, _statistics['cycles']):
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
                        print(PipelinedCpu.Pipeline.PipelineStage.to_str(stage) + '\t', end='')

                    print("")

        def __init__(self, phase_cycles):
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
            self._id_counter = 0
            self._pipeline_chronogram = self.PipelineChronogram()

        def fetch(self, next_instruction: Instruction):
            self.__move(self.PipelineStage.IF, self.PipelineStage.ID)
            logger.info("Loading into IF stage instruction '%s'." % next_instruction)
            self.__set(self.PipelineStage.IF, next_instruction)
            self._pipeline_ids[self.PipelineStage.IF] = self._id_counter
            self._id_counter += 1

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

        def print_chronogram(self):
            self._pipeline_chronogram.print()

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

    def __init__(self, registers: RegisterSet, memory: Memory, show_chronogram=False, *args, **kwargs):
        super(PipelinedCpu, self).__init__(*args, **kwargs)
        self._registers = registers
        self._memory = memory
        self._pc = 0
        self._pipeline = self.Pipeline(self._PHASE_CYCLES)
        self._status = self.CpuStatus.HALTED
        self._show_chronogram = show_chronogram

    def start(self):
        self.set_running()

    def step(self):
        if self.is_halted():
            raise HaltedCpuError

        logger.info("Processing cycle %d." % _statistics['cycles'])
        current_stage = None

        try:
            current_stage = self.Pipeline.PipelineStage.WB
            self._pipeline.writeback()

            current_stage = self.Pipeline.PipelineStage.MEM
            self._pipeline.memory()

            current_stage = self.Pipeline.PipelineStage.EX
            self._pipeline.execute()

            current_stage = self.Pipeline.PipelineStage.ID
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

            current_stage = self.Pipeline.PipelineStage.IF
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

        except StageNotFinishedSignal:
            self._pipeline.stall(current_stage)

        finally:
            logger.info(self._pipeline)
            logger.info("Cycle done.\n\n")

            self._pipeline.update_chronogram()
            self._pipeline.increase_cycle()

            if self.is_stopping() and self._pipeline.is_empty():
                if self._show_chronogram:
                    self._pipeline.print_chronogram()
                self.set_halted()

            _statistics['cycles'] += 1

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


class HaltedCpuError(Exception):
    pass


class StageNotFinishedSignal(Exception):
    pass
