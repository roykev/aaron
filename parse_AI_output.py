import numpy as np


def load_file(demofile):
    f = open(demofile, "r")
    return f.read()
def timestr2secs(t_str):
    secs=0
    t_arr=t_str.split(':')
    l=len(t_arr)
    if l==2:
        secs=int(t_arr[0])*60+int(t_arr[1])
    elif l==3:
        secs=int(t_arr[0])*3600+int(t_arr[1])*60+int(t_arr[2])
    return secs




def range2start_end(range_str):
    r_arr = range_str.split('-')
    s_str = r_arr[0]
    s_secs= timestr2secs(s_str)
    e_str = r_arr[1]
    e_secs=timestr2secs(e_str)
    return s_secs,e_secs

class gpt_parser:
    def __init__(self):
        pass
    def analyze_concepts(self,concepts):
        arr = concepts.splitlines()
   #     print(concepts)
        self.concepts =  {}
        for line in arr:
            line_arr = line.split(';')
            if len(line_arr)<2:
                continue
            times = line_arr[1].replace("'","").replace(" ","")
            ranges =times.split(',')
            self.concepts [line_arr[0]]=ranges

    #    print (self.concepts)
    def analyze_quiz(self,quiz):
     #   print(quiz)
        quiz_arr=quiz.split("****")
        self.quiz={}
        for i, block in enumerate(quiz_arr):
            block_arr=block.split('\n')
            block_arr= list(filter(lambda k: k != '', block_arr))
            if len(block_arr) == 0: continue
            q = block_arr[0]
            n_choices= len(block_arr)-2 # one answer one question
            choices=[]
            for choice in np.arange(1,n_choices+1):
                choices.append(block_arr[choice])
            correct =  block_arr[len(block_arr)-1].replace("*","").replace(" ","")
            correct_arr= correct.split(",")
            tuple_block = (q, choices,correct_arr)
            self.quiz[i]=tuple_block
        print (len(self.quiz))





    def parse(self, content):
        start_summary = 3
        end_summary = content.find("#2")
        self.summary = content[start_summary:end_summary]
        end_concepts= content.find("#3")
        concepts=content[end_summary+3:end_concepts]
        self.analyze_concepts(concepts)
#        end_quiz= content.find("***")
        quiz= content[end_concepts+3:]
        self.analyze_quiz(quiz)
      #  print(quiz)

if __name__ == '__main__':
    demorefile = "/home/roy/Downloads/gpt.txt"
    content = load_file(demorefile)
    parser = gpt_parser()
    parser.parse(content)

