import unittest
from pipeline_simulator.core import memories, architectures, instructions, compilers


class TestPipelineMethods(unittest.TestCase):

    def test_parser(self):
        """
        Test if parser creates correct Instruction and Register instances
        """

        source_file = 'tests/programs/code_test_parser.txt'
        registers = memories.RegisterSet()
        memory = memories.Memory(1024)
        parser = compilers.Parser(registers=registers, memory=memory)
        program = parser.parse(source_file)

        " Correct instruction class "
        self.assertTrue(isinstance(program[0], instructions.AluInstruction))
        self.assertTrue(isinstance(program[1], instructions.AluInstruction))
        self.assertTrue(isinstance(program[2], instructions.AluInstruction))
        self.assertTrue(isinstance(program[3], instructions.MemInstruction))
        self.assertTrue(isinstance(program[4], instructions.MemInstruction))
        self.assertTrue(isinstance(program[5], instructions.BranchInstruction))
        self.assertTrue(isinstance(program[6], instructions.BranchInstruction))
        self.assertTrue(isinstance(program[7], instructions.JumpInstruction))
        self.assertTrue(isinstance(program[8], instructions.HaltInstruction))

        " Correct registers and offsets "
        # ALU
        self.assertEqual(program[0]._rs, registers.get(2))
        self.assertEqual(program[0]._rt, registers.get(3))
        self.assertEqual(program[0]._rd, registers.get(1))

        self.assertEqual(program[1]._rs, registers.get(1))
        self.assertEqual(program[1]._rt, registers.get(8))
        self.assertEqual(program[1]._rd, registers.get(2))

        self.assertEqual(program[2]._rs, registers.get(4))
        self.assertEqual(program[2]._rt, registers.get(6))
        self.assertEqual(program[2]._rd, registers.get(0))

        # Mem
        self.assertEqual(program[3]._rs, registers.get(5))
        self.assertEqual(program[3]._rd, registers.get(8))
        self.assertEqual(program[3]._offset, 599)

    """ Short program with dependencies """
    def test_pipeline_code1(self):
        source_file = 'tests/programs/code1.txt'
        registers = memories.RegisterSet(registers_file='tests/programs/registers1.txt')
        memory = memories.Memory(1024)
        parser = compilers.Parser(registers=registers, memory=memory)
        program = parser.parse(source_file)
        memory.write_program(program)
        cpu_instance = architectures.PipelinedCpu(registers=registers, memory=memory)

        memory.set(99, 0)
        memory.set(100, 0)
        memory.set(101, 0)
        memory.set(102, 0)
        memory.set(103, 0)
        memory.set(104, 0)
        memory.set(1021, 0)

        cpu_instance.start()
        while not cpu_instance.is_halted():
            cpu_instance.step()

        self.assertEqual(memory.get_data(99), 0)
        self.assertEqual(memory.get_data(100), 5)
        self.assertEqual(memory.get_data(101), 4)
        self.assertEqual(memory.get_data(102), 3)
        self.assertEqual(memory.get_data(103), 2)
        self.assertEqual(memory.get_data(104), 1)
        self.assertEqual(registers.get(0).get_data(), 1)
        self.assertEqual(registers.get(1).get_data(), 0)
        self.assertEqual(registers.get(2).get_data(), 21)
        self.assertEqual(registers.get(3).get_data(), 41)
        self.assertEqual(registers.get(4).get_data(), 33)
        self.assertEqual(registers.get(5).get_data(), 100)
        self.assertEqual(registers.get(6).get_data(), 105)
        self.assertEqual(registers.get(7).get_data(), 0)

    def test_pipeline_code2(self):
        source_file = 'tests/programs/code2.txt'
        registers = memories.RegisterSet(registers_file='tests/programs/registers2.txt')
        memory = memories.Memory(2048)
        parser = compilers.Parser(registers=registers, memory=memory)
        program = parser.parse(source_file)
        memory.write_program(program)
        cpu_instance = architectures.PipelinedCpu(registers=registers, memory=memory)

        cpu_instance.start()
        while not cpu_instance.is_halted():
            cpu_instance.step()

        self.assertEqual(registers.get(5).get_data(), 11)
        self.assertEqual(registers.get(6).get_data(), 1)
        self.assertEqual(registers.get(7).get_data(), 100)
        self.assertEqual(registers.get(8).get_data(), 100)

        # tabla de multiplicar partiendo de la posicion 1000
        for i in range(10):
            for j in range(10):
                self.assertEqual(memory.get_data(1000+i*10+j), (i+1)*(j+1))

    """ Short program without dependencies """
    def test_pipeline_code3(self):
        source_file = 'tests/programs/code3.txt'
        registers = memories.RegisterSet(registers_file='tests/programs/registers3.txt')
        memory = memories.Memory(2048)
        parser = compilers.Parser(registers=registers, memory=memory)
        program = parser.parse(source_file)
        memory.write_program(program)
        cpu_instance = architectures.PipelinedCpu(registers=registers, memory=memory)

        cpu_instance.start()
        while not cpu_instance.is_halted():
            cpu_instance.step()

        self.assertEqual(registers.get(1).get_data(), 5)
        self.assertEqual(registers.get(2).get_data(), -1)
        self.assertEqual(registers.get(3).get_data(), 3)
        self.assertEqual(memory.get_data(1003), 3)

    def test_tomasulo_code5(self):
        source_file = 'tests/programs/code5.txt'
        registers = memories.RegisterSet(registers_file='tests/programs/registers5.txt')
        memory = memories.Memory(2048)
        parser = compilers.Parser(registers=registers, memory=memory)
        program = parser.parse(source_file)
        memory.write_program(program)
        memory.set(89, 99)
        cpu_instance = architectures.CentralizedRSCpu(registers=registers, memory=memory)

        cpu_instance.start()
        while not cpu_instance.is_halted():
            cpu_instance.step()

        self.assertEqual(registers.get(2).get_data(), 99)
        self.assertEqual(registers.get(4).get_data(), 72)
        self.assertEqual(registers.get(6).get_data(), 84)


if __name__ == '__main__':
    unittest.main()
