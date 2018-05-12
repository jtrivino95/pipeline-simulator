from pipeline_simulator.core import memories, architectures, instructions, compilers
import logging
import sys


class Main:

    def run(self):

        for opcode, latency in instructions.AluInstruction.fu_cycles.items():
            instructions.AluInstruction.fu_cycles[opcode] = 4

        for opcode, latency in instructions.MemInstruction.fu_cycles.items():
            if opcode == 'LOAD':
                instructions.MemInstruction.fu_cycles[opcode] = 6
            else:
                instructions.MemInstruction.fu_cycles[opcode] = 4

        logging.basicConfig(stream=sys.stdout, level='INFO')
        source_file = 'tests/programs/code3.txt'
        registers = memories.RegisterSet(registers_file='tests/programs/registers3.txt')
        memory = memories.Memory(2048)
        parser = compilers.Parser(registers=registers, memory=memory)
        program = parser.parse(source_file)
        memory.write_program(program)
        memory.set(89, 99)
        cpu_instance = architectures.CentralizedRSCpu(registers=registers, memory=memory, show_chronogram=True, scalability=5)

        cpu_instance.start()
        while not cpu_instance.is_halted():
            cpu_instance.step()


if __name__ == '__main__':
    Main().run()
