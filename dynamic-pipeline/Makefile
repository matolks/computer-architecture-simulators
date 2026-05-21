.PHONY: clean test

test: dynamic-pipeline.py test.in
	env python3 dynamic-pipeline.py test.in > out.txt

clean:
	-rm out.txt
