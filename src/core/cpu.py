import logging
from .instructions import Instruction, Bubble, HaltSignal, RawDependencySignal
from .memories import Memory, RegisterSet


logger = logging.getLogger(__name__)


class Cpu:

    class CpuStatus:
        READY = 0
        RUNNING = 1
        STOPPING = 2
        HALTED = 3

    class Pipeline:

        class PipelineStage:
            IF = 0
            ID = 1
            EX = 2
            MEM = 3
            WB = 4

        def __init__(self):
            self._pipeline = {
                self.PipelineStage.IF: Bubble(),
                self.PipelineStage.ID: Bubble(),
                self.PipelineStage.EX: Bubble(),
                self.PipelineStage.MEM: Bubble(),
                self.PipelineStage.WB: Bubble(),
            }

        def fetch(self, next_instruction: Instruction):
            logger.debug("Processing fetch phase.")

            self.__move(self.PipelineStage.IF, self.PipelineStage.ID)
            self.__set(self.PipelineStage.IF, next_instruction)

            logger.debug("Fetch phase completed.")

        def decode(self):
            """
            It is possible that decode() throws a HaltSignal, so
            in the instruction will move from ID to EX in that case also
            """
            logger.debug("Processing decode phase.")
            instruction = self.__get(self.PipelineStage.ID)

            try:
                halt_signal = False
                instruction.decode()

            except HaltSignal:
                halt_signal = True

            self.__move(self.PipelineStage.ID, self.PipelineStage.EX)
            logger.debug("Decode phase completed.")

            if halt_signal:
                raise HaltSignal()

        def execute(self):
            logger.debug("Processing execute phase.")

            instruction = self.__get(self.PipelineStage.EX)
            instruction.execute()
            self.__move(self.PipelineStage.EX, self.PipelineStage.MEM)

            logger.debug("Execute phase completed.")

        def memory(self):
            logger.debug("Processing memory phase.")

            instruction = self.__get(self.PipelineStage.MEM)
            instruction.memory()
            self.__move(self.PipelineStage.MEM, self.PipelineStage.WB)

            logger.debug("Memory phase completed.")

        def writeback(self):
            logger.debug("Processing writeback phase.")

            instruction = self.__get(self.PipelineStage.MEM)
            instruction.writeback()

            logger.debug("Writeback phase completed.")

        def is_empty(self):
            empty = True
            for stage in [self.PipelineStage.IF, self.PipelineStage.ID, self.PipelineStage.EX, self.PipelineStage.MEM, self.PipelineStage.WB]:
                if not isinstance(self.__get(stage), Bubble):
                    empty = False
            return empty

        def flush(self):
            """
            Replaces the instruction in the IF phase with a Bubble
            """
            self.__set(self.PipelineStage.IF, Bubble())

        def stall(self, phase):
            self.__set(phase+1, Bubble())

        def __move(self, stage_src, stage_dst):
            logger.debug("Moving instruction '%s' from phase %s to phase %s."
                        % (self._pipeline[stage_src], stage_src, stage_dst))

            self._pipeline[stage_dst] = self._pipeline[stage_src]

        def __get(self, stage):
            return self._pipeline[stage]

        def __set(self, stage, instruction: Instruction):
            logger.info("Loading into stage %d instruction '%s'." % (stage, instruction))
            self._pipeline[stage] = instruction

        def __repr__(self):
            return ("\n1. %s\n2. %s\n3. %s\n4. %s\n5. %s"
                  % (self.__get(self.PipelineStage.IF),
                     self.__get(self.PipelineStage.ID),
                     self.__get(self.PipelineStage.EX),
                     self.__get(self.PipelineStage.MEM),
                     self.__get(self.PipelineStage.WB)))

    def __init__(self, registers: RegisterSet, memory: Memory):
        self._registers = registers
        self._memory = memory
        self._pc = 0
        self._pipeline = self.Pipeline()
        self._status = self.CpuStatus.HALTED
        self._statistics = {
            'cycles': 0,
        }

    def start(self):
        self.set_running()

    def step(self):
        if self.is_halted():
            raise HaltedCpuError()

        logger.info("Processing step %d." % self._statistics['cycles'])
        current_phase = None

        try:
            current_phase = self.Pipeline.PipelineStage.WB
            self._pipeline.writeback()

            current_phase = self.Pipeline.PipelineStage.MEM
            self._pipeline.memory()

            current_phase = self.Pipeline.PipelineStage.EX
            self._pipeline.execute()

            current_phase = self.Pipeline.PipelineStage.ID
            self._pipeline.decode()

            if self.is_running():
                " If RUNNING, the next instruction is got from the memory "
                next_instruction = self._memory.get(self._pc)
                self._pc += 1
            elif self.is_stopping():
                " If STOPPING, the next instruction is a Bubble "
                next_instruction = Bubble()
            else:
                " Programming error "
                raise RuntimeError()
            current_phase = self.Pipeline.PipelineStage.IF
            self._pipeline.fetch(next_instruction)

        except HaltSignal:
            logger.info("Halt signal received.")
            if self.is_running():
                self.set_stopping()
                self._pipeline.flush()
                self._pipeline.fetch(Bubble())

            elif self.is_stopping():
                self._pipeline.fetch(Bubble())

            else:
                " Programming error "
                raise RuntimeError()

        except RawDependencySignal:
            logger.info("RAW dependency signal received.")
            self._pipeline.stall(current_phase)

        finally:
            logger.info("Step done.")
            logger.info(self._pipeline)

            if self.is_stopping() and self._pipeline.is_empty():
                self.set_halted()

            self._statistics['cycles'] += 1

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
