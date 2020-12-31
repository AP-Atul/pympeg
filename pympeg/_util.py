from random import sample
import string


def gen_label(length=5):
    return ''.join(sample(string.ascii_letters, length))


def get_str_from_params(params: dict):
	string = list()
	keys = list(params.keys())
	length = len(keys)

	string.append("%s=%s" % (keys[0], params[keys[0]]))
	for i in range(1, length):
		string.append(":%s=%s" % (keys[i], params[keys[i]]))

	return ''.join(string)


def get_str_from_filter(node):
	string = list()
	string.append("%s %s=%s %s;" % (node.in_label, node.filter, get_str_from_params(node.params), node.out_label))

	return ''.join(string)

def get_str_from_graph(graph):
	string = list()
	output = graph.pop()

	string.append("ffmpeg -y")
	string.append("-i %s" % graph.pop(0).params)
	string.append('-filter_complex"')
	for node in graph:
		string.append(get_str_from_filter(node))
	string.append('"')
	string.append("%s" % output.params)

	return " ".join(string)


