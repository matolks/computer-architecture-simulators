.PHONY: clean test

test: scalar-pipeline.py test.in
	env python3 scalar-pipeline.py test.in > out.txt

clean:
	-rm out.txt
