import java.util.Scanner;

/**
 * Imports scanner
 */

public class gradeCalculator {
	public static void main(String[] args) {
		Scanner input = new Scanner(System.in);
		/**
		 * declares class and scanner input
		 * 
		 * Gets the user input for all the variables
		 */
		
		System.out.print("Enter Labs average in percent: ");
		float labPercent = input.nextFloat();
		
		System.out.print("Enter Reading average in percent: ");
		float readingPercent = input.nextFloat();
		
		System.out.print("Enter REVEL average in percent: ");
		float revelPercent = input.nextFloat();
		
		System.out.print("Enter Midterm average in percent: ");
		float midtermPercent = input.nextFloat();
		
		System.out.print("Enter Project average in percent: ");
		float projectPercent = input.nextFloat();
		
		System.out.print("Enter Final average in percent: ");
		float finalPercent = input.nextFloat();		
		
		/**
		 * Calculates the weighted average
		 */
		
		
		float labs = (labPercent / 100) * 20 ;
		
		float reading = (readingPercent / 100) * 10 ;
		
		float revel = (revelPercent / 100) * 15 ;
		
		float midterm = (midtermPercent / 100) * 20 ;
		
		float project = (projectPercent / 100) * 15 ;
		
		float finalW = (finalPercent / 100) * 20 ;
		
		/**
		 * Adds averages together and computes to output
		 */
		
		
		float average = labs + reading + revel + midterm + project + finalW ;
		System.out.println("Your average is " + average + "%");
		
		
		
	}
}
